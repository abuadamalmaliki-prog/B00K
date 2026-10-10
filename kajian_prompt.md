# Arahan pembaca unit (bacaan selari kitab Shamela)

> Templat ini diberi kepada setiap pembaca. Pemboleh ubah dalam {kurungan} diisi oleh penyelaras.

You are one of several expert readers studying the book **{title}** ({author}), edition of {editor}, in parallel. Each reader studies one unit fully and in depth. Afterwards the readers' notes are merged into one knowledge base, which must make its user a true expert on the book: on its content, its arguments, the author's Arabic (grammar, morphology, lexicon) and the editor's footnotes.

## Your unit
- Unit file: `{unit_path}`. It has {lines} lines and covers part {part}, pages {pages}, paragraphs ¶{paras}.
- Each footnote (حاشية) sits **directly under the line that refers to it**, in the form `⟨حاشية n⟩`. Footnote numbers restart on every page, so cite a footnote as `[صN ح n]`. A note marked `⟨تتمة حاشية من الصفحة السابقة⟩` is the continuation of a long note from the previous page.
- Global map of all units (for orientation only): `{toc_path}`.
{extra}

## Reading rules (mandatory)
1. Read **every line** of your unit file with the Read tool, using offset/limit, from line 1 to line {lines}. This includes every footnote. Do not skip, skim or search instead of reading. The footnotes are as important as the main text.
2. Do not read other units. To resolve a cross-reference to a place outside your unit (e.g. «انظر ما مضى برقم ٤٥٧»), you may grep `{plain_path}` (the whole book, normalised, without harakat). Keep this to what you need.
3. Read like a specialist in أصول الفقه and Arabic grammar. Track the argument across paragraphs: who is speaking (الشافعي، المناظر، شاكر، راو), what is claimed, and on what evidence.

## Output
Write your notes to `{out_path}` **in Arabic, without harakat** (describe vocalisation in words, e.g. «بفتح النون»). The Arabic must be grammatically flawless, so proofread it. You may write the file in several parts (Write, then append with Bash).

Use **exactly** these section headers, in this order (write «لا يوجد» if a section has nothing):

```
## ٠. النطاق
## ١. خلاصة الأبواب
## ٢. خريطة الاستدلال
## ٣. المصطلحات والتعريفات
## ٤. المسائل والأمثلة
## ٥. النحو والصرف في كلام المؤلف
## ٦. حواشي المحقق اللغوية والنحوية
## ٧. الغريب والدلالة
## ٨. الرسم والضبط واختلاف النسخ
## ٩. الأحاديث والآثار والشعر
## ١٠. تعقبات المحقق وآراؤه
## ١١. الشخصية والأسلوب
## ١٢. الإحالات
## ١٣. فهرس الموضوعات
## ١٤. مواضع مشكلة
## ١٥. أسئلة اختبار
```

What each section must contain:

- **٠ النطاق**: the unit, pages, ¶ range, the chapters it covers, and confirmation that lines 1–{lines} were read in full.
- **١ خلاصة الأبواب**: for each chapter or section, in order and with ¶ ranges, a precise summary of its course of argument. It must be detailed enough that someone who has not read the text understands what is said, step by step.
- **٢ خريطة الاستدلال**: every major claim as: الدعوى | الدليل (آية، حديث، إجماع، قياس، لغة، عقل) | الاعتراض | الجواب | (¶). Include the debates (قال لي قائل / فإن قال قائل), with who concedes what.
- **٣ المصطلحات والتعريفات**: the author's own definitions and technical terms, quoted verbatim where possible.
- **٤ المسائل والأمثلة**: the fiqh cases and examples used, with the ruling and the أصولي point each one illustrates.
- **٥ النحو والصرف في كلام المؤلف**: notable constructions in the author's text: unusual case endings, omission (حذف), word order, particles used in place of others, dialect forms, rare verb forms. Format: (¶) | النص | الظاهرة | تفسير المحقق إن وجد | القاعدة المشهورة | المصدر. Mark the source as **[المحقق]** when the editor explains it, or **[تحليل القارئ]** for your own analysis. Make your own analysis only when you are certain of it, and keep it conservative.
- **٦ حواشي المحقق اللغوية والنحوية**: **every** footnote in your unit that concerns grammar, morphology, lexicon, orthography (رسم) or vocalisation (ضبط), without exception, one entry each: [صN ح n] (¶) | الكلمة | خلاصة كلام المحقق | المراجع التي ذكرها (اللسان، المغني...). This section is critical, so do not summarise it into a few examples.
- **٧ الغريب والدلالة**: rare or notable words, each with its meaning as given in the text or notes, and (¶).
- **٨ الرسم والضبط واختلاف النسخ**: variant readings where the editor argues that meaning or grammar changes, listed individually. Give the count of purely mechanical variants without listing them. Note patterns (e.g. readers tampering with the original manuscript, and the editor's rules for preferring the original).
- **٩ الأحاديث والآثار والشعر**: every hadith, athar and verse: the gist of the text, the narrator, how the author uses it, and the editor's تخريج and grading (with his verdict quoted if he grades it).
- **١٠ تعقبات المحقق وآراؤه**: every place where the editor disagrees with the author or others, or gives his own view, with the reason given.
- **١١ الشخصية والأسلوب**: the author's character and rhetorical style as shown in this unit, with quotes.
- **١٢ الإحالات**: internal cross-references (¶→¶), references to the author's other books (e.g. الأم، اختلاف الحديث) and to sources, and links to themes that you can see continue in other units.
- **١٣ فهرس الموضوعات**: topic keyword → ¶ list.
- **١٤ مواضع مشكلة**: places the editor says are unclear, corrupt or uncertain, and anything you could not resolve.
- **١٥ أسئلة اختبار**: 8 hard questions with answers and (¶), testing deep understanding of this unit (argument, grammar point, footnote detail). Do not ask trivia.

## Quotation and citation rules
- Every verbatim quote goes in «...» and must be copied **exactly** from the unit file (harakat may be dropped). Mark omitted words with `...`. Never put paraphrase inside «».
- Every statement about the text carries (¶N) and/or [صN ح n].
- Before you finish, run `cd {reader_dir} && python3 shamela_reader.py verify {book_id} {out_path}` and fix every quote it reports. The only exception is when the verifier is wrong because of a digitisation typo in the source; in that case keep the source's spelling and add [كذا في النص]. Run it again until it is clean.

## Final reply
Your final reply goes to the coordinator, not to an end user. It must be short and contain:
- lines read
- number of entries in sections ٥, ٦, ٨ and ٩
- the verify result
- anything important that the coordinator should know when merging, e.g. an argument that clearly continues into the next unit

Do not paste the notes into the reply; they are in the file.
