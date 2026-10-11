# Reading task: لوامع الأنوار البهية (al-Saffarini al-Hanbali, d. 1188)

You are one of 50 readers. Each reader has one part of the book (≈17–24
pages); together you cover all 921 pages. The question for the whole team:

> On the divine attributes (الصفات), does al-Saffarini affirm their meaning
> (إثبات المعنى) and consign only the *how* (تفويض الكيفية), or does he consign
> the meaning itself (تفويض المعنى)?

## Rules

1. **Read every line of your part.** Use the Read tool on the whole file, in
   pieces if needed (offset/limit) until you reach the end. Do not grep or
   skim instead of reading: relevant passages often use none of the obvious
   words.
2. The lines marked «تداخل» (overlap) at the very start and end are context
   from the neighbouring parts; another reader covers them, so don't report
   evidence that is only in the overlap.
3. Text has `[جX/صY]` page markers. Cite the page for every item.
4. **Who is speaking** matters. Mark each item as one of:
   - `author`: al-Saffarini's own commentary
   - `poem`: his verse (الدرة المضية), usually in ((…))
   - `quoting <name>`: a scholar he quotes (قال فلان: … انتهى). Also note
     whether he endorses, rejects or merely reports the quotation.
5. Report evidence for **both** positions with the same care. Don't decide
   the answer in advance; the team lead weighs everything.

## What to capture (anything of these kinds)

- Explicit statements: إثبات المعنى / تفويض المعنى / تفويض الكيفية / نكل
  معناه / لا نفسرها / أمروها كما جاءت / بلا كيف / من غير بحث عن معانيها, etc.
- **Explanations of what an attribute means**, even without those words, e.g.
  he says what استوى, العلو, الفوقية, النزول, الرحمة, الغضب, اليد or الوجه
  means, or how it differs from another attribute (اليد غير القدرة). Giving
  an attribute positive content counts as evidence of إثبات المعنى.
- How he uses or defines the key terms: معنى، حقيقة، كنه، كيفية، ظاهر،
  تأويل، تفسير، مجاز.
- What he says about the مفوضة / أهل التجهيل / الواقفة, and about أهل
  التأويل.
- Anything else you judge relevant to the question.

## Output

Write your findings to the output file named in your prompt, in this format
(Arabic quotes verbatim, keep each quote to the decisive sentence or two):

```
# Part NN (first page – last page)

## Evidence
1. [جX/صY] speaker: author | poem | quoting <name> (endorsed/rejected/reported)
   kind: ithbat-ma'na | tafwid-ma'na | tafwid-kayf-only | explains-meaning |
         defines-terms | against-ta'wil | against-tafwid | other
   quote: «…»
   note: one line on what the passage is doing in context

## Strongest item in this part
<number and one line why, or "none">

## Coverage
Read lines 1–N of N (confirm you reached the end).
```

If the part has nothing relevant, still write the file, with `## Evidence`
followed by `لا شيء` and the Coverage line.

Your final reply to the team lead: three lines at most (how many items, the
strongest one, and coverage confirmed). The file is what matters.
