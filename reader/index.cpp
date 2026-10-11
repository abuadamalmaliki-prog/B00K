// index.cpp — word-level index over every unit produced by parse.ml.
//
// Every word of every unit is decoded from UTF-8, normalised (diacritics and
// tatweel removed; أ إ آ ٱ -> ا, ى -> ي, ة -> ه), lightly stemmed (common
// proclitics/suffixes stripped) and put in an inverted index.
//
//   index build units.tsv outdir   -> vocab.tsv (stem, tf, df, example form)
//                                     section_terms.tsv (top TF-IDF stems per section)
//   index query units.tsv K words…  -> top-K units by BM25: "unit_id<TAB>score"
//
// Build: g++ -O2 -std=c++17 index.cpp -o index

#include <algorithm>
#include <cmath>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

using std::string;
using std::u32string;
using std::vector;

static u32string decode(const string& s) {
    u32string out;
    for (size_t i = 0; i < s.size();) {
        unsigned char c = s[i];
        char32_t cp;
        int len;
        if (c < 0x80) { cp = c; len = 1; }
        else if ((c >> 5) == 0x6) { cp = c & 0x1F; len = 2; }
        else if ((c >> 4) == 0xE) { cp = c & 0x0F; len = 3; }
        else { cp = c & 0x07; len = 4; }
        for (int k = 1; k < len && i + k < s.size(); ++k) cp = (cp << 6) | (s[i + k] & 0x3F);
        out.push_back(cp);
        i += len;
    }
    return out;
}

static string encode(const u32string& s) {
    string out;
    for (char32_t cp : s) {
        if (cp < 0x80) out += char(cp);
        else if (cp < 0x800) { out += char(0xC0 | (cp >> 6)); out += char(0x80 | (cp & 0x3F)); }
        else if (cp < 0x10000) {
            out += char(0xE0 | (cp >> 12));
            out += char(0x80 | ((cp >> 6) & 0x3F));
            out += char(0x80 | (cp & 0x3F));
        } else {
            out += char(0xF0 | (cp >> 18));
            out += char(0x80 | ((cp >> 12) & 0x3F));
            out += char(0x80 | ((cp >> 6) & 0x3F));
            out += char(0x80 | (cp & 0x3F));
        }
    }
    return out;
}

static bool is_diacritic(char32_t c) {
    return (c >= 0x610 && c <= 0x61A) || (c >= 0x64B && c <= 0x65F) || c == 0x670 ||
           (c >= 0x6D6 && c <= 0x6ED) || c == 0x640;
}
static bool is_letter(char32_t c) {
    return (c >= 0x621 && c <= 0x64A) || c == 0x671 || (c >= 'a' && c <= 'z') ||
           (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9');
}
static char32_t fold(char32_t c) {
    switch (c) {
        case 0x623: case 0x625: case 0x622: case 0x671: return 0x627;  // alef forms
        case 0x649: return 0x64A;                                      // ى -> ي
        case 0x629: return 0x647;                                      // ة -> ه
        default: return c;
    }
}

static bool starts(const u32string& w, const u32string& p) {
    return w.size() >= p.size() && std::equal(p.begin(), p.end(), w.begin());
}
static bool ends(const u32string& w, const u32string& p) {
    return w.size() >= p.size() && std::equal(p.rbegin(), p.rend(), w.rbegin());
}

// Light stemmer: strip one conjunction, one article/preposition cluster and one
// suffix, never leaving fewer than 3 letters.
static u32string stem(u32string w) {
    static const vector<u32string> pre = {U"وال", U"فال", U"بال", U"كال", U"لل", U"ال"};
    static const vector<u32string> suf = {U"هما", U"كم", U"هم", U"ها", U"ون", U"ين",
                                          U"ات", U"ان", U"يه", U"ه"};
    if (ends(w, U"لله")) return U"الله";  // الله، لله، والله، بالله، فلله
    if (w.size() > 4 && (w[0] == U'و' || w[0] == U'ف') && !starts(w, U"وال") && !starts(w, U"فال"))
        w.erase(0, 1);
    for (auto& p : pre)
        if (starts(w, p) && w.size() - p.size() >= 3) { w.erase(0, p.size()); break; }
    for (auto& s : suf)
        if (ends(w, s) && w.size() - s.size() >= 3) { w.erase(w.size() - s.size()); break; }
    return w;
}

struct Token { string stem, surface; };

static vector<Token> tokenize(const string& text) {
    vector<Token> out;
    u32string cur;
    auto push = [&] {
        if (cur.size() >= 2) out.push_back({encode(stem(cur)), encode(cur)});
        cur.clear();
    };
    for (char32_t c : decode(text)) {
        if (is_diacritic(c)) continue;
        if (is_letter(c)) cur.push_back(fold(c));
        else push();
    }
    push();
    return out;
}

// Very frequent function words carry no topical signal.
static const std::unordered_set<string>& stopwords() {
    static std::unordered_set<string> s;
    if (s.empty())
        for (const char* w : {"في", "من", "علي", "الي", "عن", "ان", "ما", "لا", "هو", "هذا",
                              "ذلك", "التي", "الذي", "او", "ثم", "قد", "كان", "مع", "كل",
                              "بن", "قال", "انه", "لم", "اذا", "به", "له", "هذه", "وهو",
                              "بل", "ولا", "اي", "عند", "منه", "فيه", "ابن", "لان", "وان",
                              "الا", "عليه", "ولم", "لما", "حتي", "قوله", "تعالي", "اله"})
            s.insert(encode(stem(decode(w))));
    return s;
}

struct Unit { int id, section; vector<string> stems; };

static vector<Unit> load(const string& path, std::unordered_map<string, string>* surface) {
    std::ifstream in(path);
    vector<Unit> units;
    string line;
    while (std::getline(in, line)) {
        // id vol page section kind text
        vector<string> f;
        std::stringstream ss(line);
        string field;
        while (std::getline(ss, field, '\t')) f.push_back(field);
        if (f.size() < 6) continue;
        Unit u{std::stoi(f[0]), std::stoi(f[3]), {}};
        for (auto& t : tokenize(f[5])) {
            u.stems.push_back(t.stem);
            if (surface && !surface->count(t.stem)) (*surface)[t.stem] = t.surface;
        }
        units.push_back(std::move(u));
    }
    return units;
}

static int build(const string& units_path, const string& outdir) {
    std::unordered_map<string, string> surface;
    auto units = load(units_path, &surface);
    std::unordered_map<string, long> tf;
    std::unordered_map<string, int> df_unit;
    std::unordered_map<int, std::unordered_map<string, int>> sec_tf;
    long words = 0;
    for (auto& u : units) {
        std::unordered_set<string> seen;
        for (auto& s : u.stems) {
            ++tf[s]; ++words;
            if (seen.insert(s).second) ++df_unit[s];
            ++sec_tf[u.section][s];
        }
    }
    vector<std::pair<string, long>> vocab(tf.begin(), tf.end());
    std::sort(vocab.begin(), vocab.end(), [](auto& a, auto& b) { return a.second > b.second; });
    std::ofstream v(outdir + "/vocab.tsv");
    for (auto& [s, n] : vocab) v << s << '\t' << n << '\t' << df_unit[s] << '\t' << surface[s] << '\n';

    // Sections as documents for TF-IDF: what makes each section distinctive.
    std::unordered_map<string, int> df_sec;
    for (auto& [sec, m] : sec_tf) for (auto& [s, n] : m) ++df_sec[s];
    const double nsec = sec_tf.size();
    std::ofstream st(outdir + "/section_terms.tsv");
    for (auto& [sec, m] : sec_tf) {
        long total = 0;
        for (auto& [s, n] : m) total += n;
        vector<std::pair<double, string>> scored;
        for (auto& [s, n] : m) {
            if (stopwords().count(s) || n < 2) continue;
            scored.push_back({double(n) / total * std::log(nsec / df_sec[s]), s});
        }
        std::sort(scored.rbegin(), scored.rend());
        st << sec;
        for (size_t i = 0; i < scored.size() && i < 12; ++i) st << '\t' << surface[scored[i].second];
        st << '\n';
    }
    std::cout << "index: " << units.size() << " units, " << words << " words, "
              << vocab.size() << " distinct stems\n";
    return 0;
}

static int query(const string& units_path, int k, const vector<string>& words) {
    auto units = load(units_path, nullptr);
    std::unordered_map<string, int> df;
    double avg = 0;
    for (auto& u : units) {
        std::unordered_set<string> seen(u.stems.begin(), u.stems.end());
        for (auto& s : seen) ++df[s];
        avg += u.stems.size();
    }
    avg /= units.size();
    std::unordered_set<string> q;
    for (auto& w : words)
        for (auto& t : tokenize(w))
            if (!stopwords().count(t.stem)) q.insert(t.stem);
    const double k1 = 1.2, b = 0.75, N = units.size();
    vector<std::pair<double, int>> scored;
    for (auto& u : units) {
        double score = 0;
        for (auto& s : q) {
            int f = std::count(u.stems.begin(), u.stems.end(), s);
            if (!f) continue;
            double idf = std::log(1 + (N - df[s] + 0.5) / (df[s] + 0.5));
            score += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * u.stems.size() / avg));
        }
        if (score > 0) scored.push_back({score, u.id});
    }
    std::sort(scored.rbegin(), scored.rend());
    for (int i = 0; i < k && i < (int)scored.size(); ++i)
        std::cout << scored[i].second << '\t' << scored[i].first << '\n';
    return 0;
}

int main(int argc, char** argv) {
    if (argc >= 4 && string(argv[1]) == "build") return build(argv[2], argv[3]);
    if (argc >= 5 && string(argv[1]) == "query")
        return query(argv[2], std::stoi(argv[3]), vector<string>(argv + 4, argv + argc));
    std::cerr << "usage: index build UNITS OUTDIR | index query UNITS K WORDS...\n";
    return 2;
}
