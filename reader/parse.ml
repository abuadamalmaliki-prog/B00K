(* parse.ml — OpenITI mARkdown -> structured units.

   Reads every line of a book exported by shamela.py and writes:
     sections.tsv  id  parent  level  vol  page  title
     units.tsv     id  vol  page  section  kind  text
   where a unit is one sentence of prose, one verse of poetry, one verse of
   the matn (the poem being commented on, quoted as ((… ... …))), one footnote
   line, or a heading.  Pages are only known when the PageVxxPyyy milestone
   that *ends* them is reached, so units are buffered per page.

   Build: ocamlopt -I +str str.cmxa parse.ml -o parse
   Usage: ./parse book.mARkdown outdir *)

type kind = Prose | Poetry | Matn | Footnote | Heading

let kind_name = function
  | Prose -> "prose" | Poetry -> "poetry" | Matn -> "matn"
  | Footnote -> "footnote" | Heading -> "heading"

type section = {
  sid : int;
  parent : int;          (* 0 = root *)
  level : int;
  title : string;
  mutable vol : int;
  mutable page : int;    (* -1 until its page milestone is seen *)
}

let starts_with s p =
  String.length s >= String.length p && String.sub s 0 (String.length p) = p

let contains s sub =
  let n = String.length s and m = String.length sub in
  let rec go i = i + m <= n && (String.sub s i m = sub || go (i + 1)) in
  go 0

let clean_field s =
  String.map (fun c -> if c = '\t' || c = '\n' || c = '\r' then ' ' else c) s
  |> String.trim

(* UTF-8 sentence terminators: . ! ? (ASCII) and Arabic ؟ (D8 9F), ؛ (D8 9B).
   Quranic text between ﴿ (EF B4 BF) and ﴾ (EF B4 BE) is never split. *)
let split_sentences (s : string) : string list =
  let n = String.length s in
  let out = ref [] and start = ref 0 and depth = ref 0 in
  let emit stop =
    let piece = String.trim (String.sub s !start (stop - !start)) in
    if piece <> "" then out := piece :: !out;
    start := stop
  in
  let at_boundary j = j >= n || s.[j] = ' ' in
  let i = ref 0 in
  while !i < n do
    let c = s.[!i] in
    if c = '\xEF' && !i + 2 < n && s.[!i + 1] = '\xB4' && s.[!i + 2] = '\xBF' then
      (incr depth; i := !i + 3)
    else if c = '\xEF' && !i + 2 < n && s.[!i + 1] = '\xB4' && s.[!i + 2] = '\xBE' then
      (depth := max 0 (!depth - 1); i := !i + 3)
    else if !depth = 0 && (c = '.' || c = '!' || c = '?') && at_boundary (!i + 1) then
      (emit (!i + 1); incr i)
    else if !depth = 0 && c = '\xD8' && !i + 1 < n
            && (s.[!i + 1] = '\x9F' || s.[!i + 1] = '\x9B') && at_boundary (!i + 2) then
      (emit (!i + 2); i := !i + 2)
    else incr i
  done;
  emit n;
  List.rev !out

let page_re = Str.regexp "^PageV\\([0-9]+\\)P\\([0-9]+\\)$"
let vol_re = Str.regexp "^### | الجزء \\([0-9]+\\)"
let head_re = Str.regexp "^### \\(||+\\) \\(.*\\)$"

let () =
  if Array.length Sys.argv < 3 then (prerr_endline "usage: parse BOOK OUTDIR"; exit 2);
  let ic = open_in Sys.argv.(1) and outdir = Sys.argv.(2) in
  let units_oc = open_out (Filename.concat outdir "units.tsv") in
  let sections = ref [] and stack = ref [] in   (* stack: (level, sid) *)
  let pending = ref [] in                        (* units of the current page, reversed *)
  let pending_heads = ref [] in
  let next_unit = ref 0 and next_sid = ref 0 in
  let vol = ref 1 and in_footnotes = ref false in
  let current_section () = match !stack with (_, sid) :: _ -> sid | [] -> 0 in
  let add kind text =
    let text = clean_field text in
    if text <> "" then pending := (kind, current_section (), text) :: !pending
  in
  let flush page =
    List.iter (fun (kind, sec, text) ->
        incr next_unit;
        Printf.fprintf units_oc "%d\t%d\t%d\t%d\t%s\t%s\n"
          !next_unit !vol page sec (kind_name kind) text)
      (List.rev !pending);
    List.iter (fun s -> s.vol <- !vol; s.page <- page) !pending_heads;
    pending := []; pending_heads := []; in_footnotes := false
  in
  (try
     while true do
       let line = input_line ic in
       if Str.string_match page_re line 0 then
         flush (int_of_string (Str.matched_group 2 line))
       else if Str.string_match vol_re line 0 then
         (vol := int_of_string (Str.matched_group 1 line); stack := [])
       else if Str.string_match head_re line 0 then begin
         let level = String.length (Str.matched_group 1 line) - 1 in
         let title = clean_field (Str.matched_group 2 line) in
         while (match !stack with (l, _) :: _ -> l >= level | [] -> false) do
           stack := List.tl !stack
         done;
         incr next_sid;
         let s = { sid = !next_sid; parent = current_section (); level; title;
                   vol = !vol; page = -1 } in
         sections := s :: !sections;
         pending_heads := s :: !pending_heads;
         stack := (level, s.sid) :: !stack;
         add Heading title
       end
       else if starts_with line "____" then in_footnotes := true
       else if starts_with line "# " then begin
         let body = String.sub line 2 (String.length line - 2) in
         if !in_footnotes then add Footnote body
         else if (contains body "((" || contains body "))") && contains body " ... " then
           add Matn body   (* the source sometimes opens with a single "(" *)
         else if contains body " ... " then add Poetry body
         else List.iter (add Prose) (split_sentences body)
       end
     done
   with End_of_file -> ());
  close_in ic; close_out units_oc;
  let soc = open_out (Filename.concat outdir "sections.tsv") in
  List.iter (fun s ->
      Printf.fprintf soc "%d\t%d\t%d\t%d\t%d\t%s\n" s.sid s.parent s.level s.vol s.page s.title)
    (List.rev !sections);
  close_out soc;
  Printf.printf "parse: %d units, %d sections\n" !next_unit !next_sid
