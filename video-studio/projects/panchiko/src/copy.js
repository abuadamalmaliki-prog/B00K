// copy.js: every word that appears in the film (screenwriter).
//
// Rules:
// - Everything here is INVENTED and brand-free. The exceptions are Panchiko's
//   own name, the EP title, its track titles (Wikipedia track listing) and the
//   true-story cards (Wikipedia, see `facts`).
// - NO LYRICS anywhere.
// - Invented names were spot-checked by web search (no matches found). They
//   were not checked against every small business on earth.
// - No logos: "DVD"/"BLU-RAY" appear only as plain format words, never as the
//   format logos. No certification logos.
// - Every string uses only Latin-1 plus these glyphs: – — ’ “ ” …
//   (all present in Inter and Zen Maru Gothic).
// - Beat numbers `n` refer to work/music/timing.json beats[].n (film window).

const store = {
  storeName: 'LANTERNFISH',
  sign: {
    main: 'LANTERNFISH',
    sub: 'MUSIC & FILM',
    strap: 'CDs · VINYL · DVD · BLU-RAY',     // under the fascia, small
    number: '27',                             // above the door
    hours: 'OPEN 7 DAYS · 10AM – 10PM',
    door: { push: 'PUSH', open: 'OPEN', closed: 'SORRY, WE’RE CLOSED' },
  },
  // Painted or vinyl-lettered on the window glass, and stickers.
  windowSlogans: [
    'LOST SOMETHING? IT’S PROBABLY IN HERE.', // hero line, the film's theme
    'WE BUY & SELL CDs · DVDs · BLU-RAY · VINYL',
    'PRE-OWNED CDs FROM £1',
    '2 FOR £10 ON SELECTED CDs',
    'NEW RELEASES EVERY FRIDAY',               // UK release day since July 2015 (true)
    'OPEN LATE',
  ],
  // Hanging aisle and section signs. `id` is used by cdSpines[].genre / dvdTitles[].section.
  sections: [
    { id: 'new',       label: 'NEW RELEASES' },
    { id: 'indie',     label: 'INDIE / ALTERNATIVE' },
    { id: 'rock',      label: 'ROCK' },
    { id: 'pop',       label: 'POP' },
    { id: 'dance',     label: 'DANCE / ELECTRONIC' },
    { id: 'hiphop',    label: 'HIP-HOP / R&B' },
    { id: 'metal',     label: 'METAL' },
    { id: 'jazz',      label: 'JAZZ / BLUES' },
    { id: 'folk',      label: 'FOLK / COUNTRY' },
    { id: 'classical', label: 'CLASSICAL' },
    { id: 'world',     label: 'WORLD' },
    { id: 'ost',       label: 'SOUNDTRACKS' },
    { id: 'comps',     label: 'COMPILATIONS' },
    { id: 'film',      label: 'DVD · FILM A–Z' },
    { id: 'tv',        label: 'DVD · TV BOX SETS' },
    { id: 'bluray',    label: 'BLU-RAY' },
    { id: 'worldcin',  label: 'WORLD CINEMA' },
    { id: 'anime',     label: 'ANIME' },
    { id: 'kids',      label: 'KIDS & FAMILY' },
  ],
  // Divider cards inside the racks (A–Z tabs).
  rackDividers: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I–J', 'K', 'L', 'M', 'N–O', 'P', 'Q–R', 'S', 'T', 'U–V', 'W', 'X–Z'],
  misc: {
    counter: 'PAY HERE',
    listeningPost: { title: 'LISTENING POST', hint: 'PRESS PLAY TO PREVIEW', nowPlaying: 'NOW PLAYING: Moth Parade Radio — Static Bloom' },
    notices: ['CCTV IN OPERATION', 'PLEASE ASK FOR HELP', 'NO FOOD OR DRINK', 'GIFT VOUCHERS AVAILABLE', 'WE BUY YOUR CDs FOR CASH — ASK AT THE COUNTER'],
    staffPicks: [ // handwritten shelf-talkers
      { head: 'STAFF PICK', body: 'Starling Mechanics — Murmuration. Headphones, night bus, repeat.', by: 'Priya' },
      { head: 'STAFF PICK', body: 'Doug Pellingham Trio. Jazz for people who think they hate jazz.', by: 'Tom' },
      { head: 'STAFF PICK', body: 'The Saltmarsh Bell. Do NOT watch this alone.', by: 'Kez' },
    ],
  },
  // Neighbouring shopfronts in shot 1: generic words only, no names.
  street: ['LAUNDERETTE', 'KEYS CUT · SHOE REPAIRS', 'FISH & CHIPS', 'TO LET', 'BUS STOP'],
};

// 8 posters: invented films, albums, a tour and a box set.
const posters = [
  { kind: 'film',  title: 'THE LIGHTHOUSE AT GANNET POINT', tagline: 'Some lights should stay off.', footer: 'OUT NOW ON DVD' },
  { kind: 'album', artist: 'NORTHBOUND MAGPIES', title: 'RING ROAD SONGS', footer: 'THE NEW ALBUM · IN STORE NOW' },
  { kind: 'film',  title: 'WOLVES OF THE WASH', tagline: 'The tide brings them in.', footer: 'BLU-RAY & DVD' },
  { kind: 'album', artist: 'IVY CASTELLANE', title: 'STAINED GLASS HEART', footer: 'DELUXE EDITION WITH BONUS DVD' },
  { kind: 'film',  title: 'ASHES OF VIREO', tagline: 'One kingdom. One winter.', footer: 'NOW ON BLU-RAY' },
  { kind: 'tour',  artist: 'MOTH PARADE RADIO', title: 'LIVE THIS AUTUMN', footer: 'TICKETS AVAILABLE HERE' },
  { kind: 'anime', title: 'SKY LANTERN SQUADRON', tagline: 'The complete series.', footer: '6-DISC BOX SET' },
  { kind: 'album', artist: 'STARLING MECHANICS', title: 'MURMURATION', footer: 'ALBUM OF THE MONTH' },
];

// 65 CD spines. `genre` is a sections id. Years are 2000s-era, a few later.
const cdSpines = [
  // indie
  { artist: 'Marigold Switchboard', title: 'Porchlight Semaphore', genre: 'indie', year: 2004 },
  { artist: 'The Tinfoil Cartographers', title: 'Maps of Nowhere Near', genre: 'indie', year: 2006 },
  { artist: 'Moth Parade Radio', title: 'Static Bloom', genre: 'indie', year: 2003 },
  { artist: 'The Wednesday Pylons', title: 'High Voltage Pastoral', genre: 'indie', year: 2005 },
  { artist: 'Cobalt Allotment', title: 'Greenhouse Effects', genre: 'indie', year: 2007 },
  { artist: 'Northbound Magpies', title: 'Ring Road Songs', genre: 'indie', year: 2008 },
  { artist: 'The Pocket Satellites', title: 'Signal Lost', genre: 'indie', year: 2002 },
  { artist: 'Dandelion Telex', title: 'Morse Code Valentine', genre: 'indie', year: 2006 },
  { artist: 'The Monday Arcadians', title: 'Leisure Centre', genre: 'indie', year: 2009 },
  { artist: 'Hazelmere Cyclists', title: 'Bicycle Summer', genre: 'indie', year: 2004 },
  { artist: 'The Hinterland Postmen', title: 'Second Class', genre: 'indie', year: 2011 },
  { artist: 'Starling Mechanics', title: 'Murmuration', genre: 'indie', year: 2013 },
  { artist: 'Hesketh & the Night Buses', title: 'Last Stop Bulwell', genre: 'indie', year: 2007 },
  { artist: 'Mothball Circus', title: 'Attic Treasures', genre: 'indie', year: 2001 },
  // rock
  { artist: 'Kilnworth', title: 'Ash & Ember', genre: 'rock', year: 2003 },
  { artist: 'Crowhurst & Vane', title: 'Weathercock', genre: 'rock', year: 2001 },
  { artist: 'Carbon Viaduct', title: 'Monochrome Spring', genre: 'rock', year: 2005 },
  { artist: 'The Brass Pigeons', title: 'Town Square Stomp', genre: 'rock', year: 2007 },
  { artist: 'Cassiopeia Drive', title: 'Headlights on the M1', genre: 'rock', year: 2006 },
  { artist: 'Velvet Ferris Wheel', title: 'Funfair After Dark', genre: 'rock', year: 2010 },
  // pop
  { artist: 'Ruby Quarrington', title: 'Postcards to Nobody', genre: 'pop', year: 2005 },
  { artist: 'Ivy Castellane', title: 'Stained Glass Heart', genre: 'pop', year: 2008 },
  { artist: 'Tessellate Twins', title: 'Mirror Tiles', genre: 'pop', year: 2004 },
  { artist: 'Lola Marchbank', title: 'Sugar & Diesel', genre: 'pop', year: 2009 },
  { artist: 'Big Sister Hovercraft', title: 'Seasick Disco', genre: 'pop', year: 2002 },
  { artist: 'Opal Kettering', title: 'Soft Furnishings', genre: 'pop', year: 2012 },
  { artist: 'Mei-Lin Hartigan', title: 'Paper Lantern Letters', genre: 'pop', year: 2014 },
  { artist: 'Saffron Tidewell', title: 'Harbour Hours', genre: 'pop', year: 2006 },
  { artist: 'The Fothergill Sisters', title: 'Three Part Harmony', genre: 'pop', year: 2003 },
  // dance / electronic
  { artist: 'DJ Tarmac Fox', title: 'Sodium Lights EP', genre: 'dance', year: 2006 },
  { artist: 'Subsonic Heron', title: 'Wader Frequencies', genre: 'dance', year: 2003 },
  { artist: 'Neon Pantry', title: 'Fridge Light Serenade', genre: 'dance', year: 2008 },
  { artist: 'Pixel Hymnal', title: '8-Bit Vespers', genre: 'dance', year: 2010 },
  { artist: 'K-Nova & the Slipstream', title: 'Afterburner', genre: 'dance', year: 2005 },
  { artist: 'Tangerine Satnav', title: 'Recalculating', genre: 'dance', year: 2011 },
  // hip-hop / r&b
  { artist: 'MC Petrichor', title: 'Rain Check', genre: 'hiphop', year: 2007 },
  { artist: 'Lowdown Lamplighter', title: 'Night Bus Chronicles', genre: 'hiphop', year: 2006 },
  { artist: 'Clementine Oduya', title: 'Honey Hours', genre: 'hiphop', year: 2009 },
  { artist: 'Verse Mechanic', title: 'Blueprint for a Bedsit', genre: 'hiphop', year: 2003 },
  { artist: 'Kairo Pennant', title: 'Postcode Poetry', genre: 'hiphop', year: 2012 },
  // metal
  { artist: 'Thunderlodge', title: 'Iron Anthems Vol. II', genre: 'metal', year: 2004 },
  { artist: 'Void Harvester', title: 'Grave Tractor', genre: 'metal', year: 2007 },
  { artist: 'Ossuary Glacier', title: 'Frostbitten Cathedral', genre: 'metal', year: 2002 },
  { artist: 'Blackmoor Anvil', title: 'Forged in Winter', genre: 'metal', year: 2009 },
  // jazz / blues
  { artist: 'Doug Pellingham Trio', title: 'Blue Hour at the Lido', genre: 'jazz', year: 2001 },
  { artist: 'Barnaby Wick', title: 'Candle-End Blues', genre: 'jazz', year: 2003 },
  { artist: 'The Ottoline Five', title: 'Swing Shift', genre: 'jazz', year: 2006 },
  { artist: 'Rosalind Harrowby Quartet', title: 'Late Tram Ballads', genre: 'jazz', year: 2008 },
  // folk / country
  { artist: 'Oona Brackenridge', title: 'Heather in the Headlights', genre: 'folk', year: 2005 },
  { artist: 'Pewter Harbour', title: 'Foghorn Folk', genre: 'folk', year: 2007 },
  { artist: 'Rufus Oakenshaw', title: 'Songs for Slow Trains', genre: 'folk', year: 2004 },
  { artist: 'Wren & Wrought Iron', title: 'Garden Gate', genre: 'folk', year: 2010 },
  { artist: 'Driftwood Assembly', title: 'Shoreline Sessions', genre: 'folk', year: 2006 },
  { artist: 'Juniper Vale Collective', title: 'Low Orbit Lullabies', genre: 'folk', year: 2008 },
  // classical
  { artist: 'Orchestra of the Silver Estuary', title: 'Tidal Suite No. 3', genre: 'classical', year: 2002 },
  { artist: 'The Orangery Choir', title: 'Winter Carols', genre: 'classical', year: 2005 },
  { artist: 'Fennimore Grey, piano', title: 'Nocturnes for the Night Shift', genre: 'classical', year: 2009 },
  // world
  { artist: 'Sable Kingfisher', title: 'Riverbank Dub', genre: 'world', year: 2004 },
  { artist: 'Tomás Quillinan & the Harbour Strings', title: 'Borrowed Skies', genre: 'world', year: 2008 },
  // soundtracks (tie in with dvdTitles)
  { artist: 'Original Soundtrack', title: 'The Lighthouse at Gannet Point', genre: 'ost', year: 2004 },
  { artist: 'Original Soundtrack', title: 'Galaxy Postman', genre: 'ost', year: 2006 },
  // compilations
  { artist: 'Various Artists', title: 'Service Station Classics (2CD)', genre: 'comps', year: 2005 },
  { artist: 'Various Artists', title: 'Rainy Day Acoustic', genre: 'comps', year: 2007 },
  { artist: 'Various Artists', title: 'Motorway Mixtape Vol. 3', genre: 'comps', year: 2006 },
  { artist: 'Various Artists', title: 'Garden Party Soul', genre: 'comps', year: 2008 },
];

// 32 DVD / Blu-ray titles. `cert` is plain text only (never a certification logo).
const dvdTitles = [
  { title: 'The Lighthouse at Gannet Point', genre: 'thriller', year: 2004, format: 'DVD', cert: '15', section: 'film' },
  { title: 'Crossing Tollerton', genre: 'drama', year: 2006, format: 'DVD', cert: '12', section: 'film' },
  { title: 'Kestrel Protocol', genre: 'action', year: 2005, format: 'DVD', cert: '15', section: 'film' },
  { title: 'My Uncle the Hovercraft', genre: 'family', year: 2002, format: 'DVD', cert: 'U', section: 'kids' },
  { title: 'Night Shift at the Planetarium', genre: 'comedy', year: 2007, format: 'DVD', cert: '12', section: 'film' },
  { title: 'The Saltmarsh Bell', genre: 'horror', year: 2008, format: 'DVD', cert: '18', section: 'film' },
  { title: 'Operation Copper Kettle', genre: 'war comedy', year: 2003, format: 'DVD', cert: 'PG', section: 'film' },
  { title: 'The Last Tram to Arnold', genre: 'drama', year: 2009, format: 'BLU-RAY', cert: '12', section: 'bluray' },
  { title: 'Galaxy Postman', genre: 'animation', year: 2006, format: 'DVD', cert: 'U', section: 'kids' },
  { title: 'Beneath the Allotment', genre: 'horror', year: 2005, format: 'DVD', cert: '15', section: 'film' },
  { title: 'Ten Pin Heroes', genre: 'sports comedy', year: 2004, format: 'DVD', cert: '12', section: 'film' },
  { title: 'Cold Ribbon', genre: 'crime', year: 2007, format: 'DVD', cert: '18', section: 'film' },
  { title: 'Summer of the Tin Kites', genre: 'romance', year: 2001, format: 'DVD', cert: 'PG', section: 'film' },
  { title: 'Gravel Moon', genre: 'western', year: 2003, format: 'DVD', cert: '15', section: 'film' },
  { title: 'The Clockmaker of Wendle Street', genre: 'fantasy', year: 2006, format: 'DVD', cert: 'PG', section: 'kids' },
  { title: 'Iron Vigil', genre: 'action', year: 2008, format: 'BLU-RAY', cert: '15', section: 'bluray' },
  { title: 'Harriet & the Heatwave', genre: 'romcom', year: 2005, format: 'DVD', cert: '12', section: 'film' },
  { title: 'Relay Station Nine', genre: 'sci-fi', year: 2002, format: 'DVD', cert: '15', section: 'film' },
  { title: 'The Quiet Motorway', genre: 'drama', year: 2010, format: 'BLU-RAY', cert: '15', section: 'bluray' },
  { title: 'Detective Pennywhistle: Series 2', genre: 'tv crime', year: 2004, format: 'DVD', cert: '12', section: 'tv' },
  { title: 'Coastguard Cottage: The Complete Series', genre: 'tv drama', year: 2003, format: 'DVD', cert: 'PG', section: 'tv' },
  { title: 'Robo-Badger Returns', genre: 'kids', year: 2007, format: 'DVD', cert: 'U', section: 'kids' },
  { title: 'Sky Lantern Squadron', genre: 'anime', year: 2005, format: 'DVD', cert: '12', section: 'anime' },
  { title: 'Ashes of Vireo', genre: 'fantasy epic', year: 2009, format: 'BLU-RAY', cert: '12', section: 'bluray' },
  { title: 'Deadline at Dunmore', genre: 'political thriller', year: 2011, format: 'BLU-RAY', cert: '15', section: 'bluray' },
  { title: 'The Lido Summer', genre: 'indie drama', year: 2012, format: 'BLU-RAY', cert: '12', section: 'bluray' },
  { title: 'Blackout on Level 4', genre: 'thriller', year: 2010, format: 'BLU-RAY', cert: '15', section: 'bluray' },
  { title: 'Wolves of the Wash', genre: 'horror', year: 2013, format: 'BLU-RAY', cert: '18', section: 'bluray' },
  { title: 'Pocket Planet 3D', genre: 'animation', year: 2014, format: 'BLU-RAY', cert: 'U', section: 'kids' },
  { title: 'The Nine Lives of Mrs Ashby', genre: 'comedy-drama', year: 2008, format: 'DVD', cert: '12', section: 'film' },
  { title: 'Midnight at Marrow Lane', genre: 'mystery', year: 2006, format: 'DVD', cert: '15', section: 'film' },
  { title: 'Low Tide Keeper', genre: 'subtitled drama', year: 2007, format: 'DVD', cert: '12', section: 'worldcin' },
];

// The bargain bin where he finds it (handwritten marker on card).
const bargainBin = {
  title: 'PRE-OWNED / DONATED CDs',
  price: '£1 EACH',
  deal: '3 FOR £2',
  note: 'All money from this box goes to local charity',   // nod to the true charity-shop find
};

// Price stickers and receipt (set dressing). The receipt is optional: no shot shows paying.
const priceTags = ['£1', '£2.99', '£4.99', '£5.99', '£7.99', '£9.99', '£12.99', '2 FOR £10', 'SALE', 'NEW', 'PRE-OWNED', 'STAFF PICK'];
const panchikoSticker = { text: '£1', place: 'case BACK or spine only, never over the supplied cover' };
const receipt = {
  lines: ['LANTERNFISH', 'MUSIC & FILM', 'SHERWOOD · NOTTINGHAM', '------------------------', 'PRE-OWNED CD        £1.00', 'TOTAL               £1.00', 'CASH                £1.00', 'CHANGE              £0.00', '------------------------', 'JUL 2016  21:47', 'THANK YOU · KEEP LISTENING'],
  note: 'Day of month left out on purpose: the article does not say what day the CD was found.',
};

// Portable CD player (NOT a real brand; do not use real product names).
const player = {
  brand: 'NORVELLE',
  model: 'PCD-40',
  labels: ['ANTI-SHOCK 40 SEC', 'HOLD', 'VOL', 'OPEN'],
  lcd: { idle: '--:--', reading: 'READING', play: 'PLAY  01', time: '0:00' },
  // Track 01 = the title track (song.mp4 is 261.97 s; the Wikipedia title track is 4:21).
  // Film licence: the time counts from 0:00 although the audio window starts at 2:56.
};

// The Panchiko case and disc. The front is the supplied cover image, as is.
const panchiko = {
  // Case back when he turns it over (shot 4). The layout is ours; the text is
  // Wikipedia's track listing. No surnames: the article says the members did
  // not put their last names on the back.
  caseBack: {
    heading: 'PANCHIKO',
    tracks: [
      { n: 1, title: 'D>E>A>T>H>M>E>T>A>L', len: '4:21' },
      { n: 2, title: 'Stabilisers for Big Boys', len: '4:12' },
      { n: 3, title: 'Laputa', len: '2:43' },
      { n: 4, title: 'The Eyes of Ibad', len: '6:57' },
    ],
  },
  disc: { label: '', note: 'CD-R (about 30 copies were burnt). Leave the label blank: the article doesn’t say what the real disc had on it.' },
};

// Every card that appears. Times are the film window; beat `n` is from timing.json.
const cards = {
  opening: { text: 'Nottingham · 2016', shot: 1 },

  // Shot 8: 3D letters rise from the grass. One group per beat, n 65..74
  // (44.138 → 50.345 s); n 75–76 hold; the shot ends at 52.40.
  titleRise: {
    text: 'D>E>A>T>H>M>E>T>A>L',
    groups: ['D>', 'E>', 'A>', 'T>', 'H>', 'M>', 'E>', 'T>', 'A>', 'L'],
    beatN: [65, 66, 67, 68, 69, 70, 71, 72, 73, 74],
  },

  // Shot 9 (52.41–57.24): true-story cards, small, in 3D. See `facts`.
  end: [
    { beatN: 77, t: 52.414, line1: 'Found in a charity shop', line2: 'Sherwood, Nottingham · 2016' },
    { beatN: 80, t: 54.483, line1: '2020, a message to the singer:', line2: '“…are you the lead singer of Panchiko?”' },
    { beatN: 83, t: 56.552, line1: '“Yeah.”', line2: '' },   // can stay on screen into the title
  ],

  // Shot 10 (57.24–60.69).
  title: { beatN: 84, t: 57.242, main: 'PANCHIKO', sub: 'D>E>A>T>H>M>E>T>A>L', year: '2000' },
  finePrint: 'A dramatisation. Store, products and people shown are invented.',

  // For the 4:22 version: more cards if there is time to read them.
  endLong: [
    'In 2000, a band of school friends burnt about 30 copies of a demo CD.',
    'In 2016, one turned up in a charity shop in Sherwood, Nottingham.',
    'The finder posted it online. Nobody knew who made it.',
    'Strangers searched for the band for years.',
    '21 January 2020: “…are you the lead singer of Panchiko?”',
    '“Yeah.”',
    'The band had no idea.',
  ],
};

// Reference only, NEVER rendered (it names real brands). Where the true lines come from. Source: https://en.wikipedia.org/wiki/Deathmetal_(EP)
const facts = {
  place: '"the user had found the CD at an Oxfam store in Sherwood, Nottingham" (4chan section)',
  year: '"rediscovered by a 4chan user in July 2016"; post dated 21 July 2016',
  message: 'On 21 January 2020 a search-team member messaged the lead singer: "Hello, you\'ll probably never read this, but are you the lead singer of Panchiko?" Davies replied "Yeah."',
  copies: '"Approximately 30 copies ... burnt onto recordable CDs" (lead); school friends: "a group of high school friends in Nottingham" (Background)',
  unaware: 'Davies "had been completely unaware of the EP\'s circulation online"',
};

const watermark = 'Instagram: ihvyone_1 · Tiktok: rapidfirequestion';

export default {
  storeName: store.storeName,
  sign: store.sign,
  windowSlogans: store.windowSlogans,
  sections: store.sections,
  rackDividers: store.rackDividers,
  misc: store.misc,
  street: store.street,
  posters,
  cdSpines,
  dvdTitles,
  bargainBin,
  priceTags,
  panchikoSticker,
  receipt,
  player,
  panchiko,
  cards,
  facts,
  watermark,
};
