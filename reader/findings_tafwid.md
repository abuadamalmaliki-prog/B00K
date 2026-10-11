# Is al-Saffarini a mufawwid? Evidence from لوامع الأنوار البهية

**Method.** `evidence.py tafwid` collects every passage on the topic, not a
ranked top-k: 216 matching units, shown in reading order with their
neighbours. Every unit is tagged with its speaker (al-Saffarini, the poem, or
a named scholar he is quoting). All of it was read. Page numbers are from
volume 1 of the Damascus 1402 edition.

## Why retrieval gets this wrong

A search for "تفويض معناها المراد إلى الله" (`read.py ask` or `explore`)
returns ص219, ص8, ص97, ص141 and ص242. Those are the passages that sound like
tafwid, and two of them (ص141 Ibn Hajar, ص242 al-Bayhaqi) are quotations
rather than his own words. Neither search returns ص117, ص211, ص215 or
ص265–266, the passages that define his terms. A reader of the top results
would conclude "mufawwid".

## Statements that read as tafwid al-maʿnā (his own voice)

| Page | Text |
|---|---|
| ص8 | أصحابنا من أتباع المأثور، والمرور كما جاء **مع التفويض** |
| ص107 | ووجب إثباته له على الوجه الذي ورد، **ونكل معناه** للعزيز الحكيم، ولا نعدل به عن حقيقة وصفه |
| ص219 | مذهب السلف… لا تؤول ولا تفسر بل يجب الإيمان بها، **وتفويض معناها المراد منها** إلى الله |
| ص241 | (Ahmad via Ibn Hamdan) تمر كما جاءت **من غير بحث عن معانيها**… وكل ما يعقل ويتصور فهو تكييف; then in his own words: وهذا مذهب السلف الأثرية **فهو الحق** |
| ص261 | the poem: «من غير تأويل **وغير فكر**»; his gloss: ولا تتعرض **لمعانيها** وأسرارها… فإن ذلك **ليس في طوق البشر** |

## Statements of ithbāt al-maʿnā / tafwid of the kayf only

| Page | Text |
|---|---|
| ص101 | الإثبات… من غير تعطيل لها **عن حقائقها** |
| ص117 | under his own heading «طوائف المنحرفين وأنهم أهل تخييل **وتجهيل**»: أهل التجهيل are those who say the Prophet did not know the meanings of the attribute verses; the تأويل only God knows **is the unknown kayf** (الاستواء معلوم والكيف مجهول) |
| ص200 | الاستواء معلوم… وأما الوقوف على **حقيقة أمر يعود إلى الكيفية** فمجهول |
| ص211 | (al-Wasiti, quoted approvingly under his heading) **والوقوف في ذلك جهل وغي**… فما وصف لنا نفسه بها إلا لنثبت… إثبات بلا تحريف ولا تكييف **ولا وقوف** |
| ص225–226 | إثبات وجود لا إثبات تكييف… صفات الرب **معلومة من حيث الجملة والثبوت**، غير معقولة من حيث التكييف |
| ص231 | اليدان صفتان ذاتيتان **تزيدان على النعمة والقدرة**: positive content, not an empty word |
| ص247 | ذاته وصفاته **معلومة من حيث الجملة**… بلا كيفية ولا تحديد |
| ص265–266 | adopts Ibn Taymiyya's six positions on the attribute texts: the "الله أعلم بمراده" position is one of those that take the texts **against their apparent sense**; «والصواب… القطع **بالطريقة الثانية**» (their apparent sense, as befits God); then in his own words: صفاته لا يعلم **كنهها وحقيقتها** إلا هو… وإنما تعلم **من حيث الجملة** |

## The passage that reconciles them

ص215: «وكذلك **مدلول** أسمائه وصفاته التي يختص بها **التي هي حقيقته** لا يعلمها إلا هو».

Here the unknowable *meaning* is equated with the attribute's own *reality*.
Read with ص200 (حقيقة… تعود إلى الكيفية), ص266 (كنهها وحقيقتها) and ص261 (ليس
في طوق البشر: the lexical sense of يد or استواء is not beyond human
capacity, but its reality is), the word «معنى» in his tafwid statements
refers to the reality and *how* of the attribute, not to the lexical sense.

## Verdict

Read as a whole, the book supports **muthbit al-maʿnā, mufawwid al-kayf**:

- He adopts the Taymiyyan framework structurally, in his own section headings:
  ahl al-tajhil are deviants, wuqūf is ignorance, and the right position is
  الطريقة الثانية.
- He gives attributes positive content (the two hands are additional to
  blessing and power).
- He defines the unknowable part as the حقيقة / كنه / كيفية.

**What the text does not settle:**

- **His wording.** "تفويض معناها المراد" (ص219) and "من غير بحث عن معانيها…
  فهو الحق" (ص241) are tafwid formulas. They are worded as such, not merely
  ambiguous. Whether they are loose terminology (معنى = حقيقة) or a real
  inconsistency is an interpretive judgement. The reconciliation above is the
  reading that makes the book consistent; it is not stated by him in so many
  words.
- **The editors' notes.** The edition's notes (أبا بطين، ابن سحمان) are not
  marked separately in this digital text, so any objection they raised to
  these formulas cannot be isolated here.
