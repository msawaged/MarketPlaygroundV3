const ACRONYMS = new Set(['ai', 'ev', 'evs', 'us', 'uk', 'eu', 'etf', 'etfs', 'reit', 'reits', 'gpu', 'gpus', 'fed', 'glp-1']);

/** "ai chips" -> "AI chips" */
export function themeLabel(t) {
  const words = String(t || '').split(' ').map((w) => (ACRONYMS.has(w.toLowerCase()) ? w.toUpperCase() : w));
  const s = words.join(' ');
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// ---- "I doubt it": a news hunch's opposite, written the way a person would say it ----
// Mirrors backend seeder._lower_first / _negatable so the app and the brain phrase the other side the same way.
const PROPER = new Set(['iran', 'israel', 'china', 'canada', 'mexico', 'europe', 'japan', 'russia', 'ukraine', 'india',
  'brazil', 'taiwan', 'korea', 'germany', 'britain', 'france', 'italy', 'venezuela', 'gaza', 'gulf', 'saudi', 'english',
  'fed', 'congress', 'senate', 'democrats', 'republicans', 'democratic', 'republican', 'trump', 'musk', 'washington',
  'wall', 'medicare', 'medicaid', 'opec', 'hormuz', 'microsoft', 'apple', 'tesla', 'nvidia', 'amazon', 'google',
  'alphabet', 'meta', 'intel', 'oracle', 'boeing', 'netflix', 'walmart', 'palantir', 'anthropic', 'openai',
  // Nationalities and places the -ian / -ese rule misses; same list as backend seeder._PROPER.
  'american', 'african', 'asian', 'european', 'korean', 'chilean', 'mexican', 'british', 'spanish', 'irish',
  'danish', 'swedish', 'finnish', 'turkish', 'scottish', 'french', 'german', 'dutch', 'swiss', 'greek', 'thai',
  'israeli', 'argentine', 'texas', 'california', 'florida']);
const NEGATED = /\b(not|no|never|won't|can't|cannot|don't|doesn't|isn't|aren't|wasn't|weren't|shouldn't|wouldn't)\b|n['’]t\b/i;

/** Lower-case the first letter so it reads after "I don't think", unless the first word is a name or acronym
 *  ("AI firms", "Nvidia", "China's", "Social Security", "5G" stay as they are). */
export function lowerFirst(s) {
  const text = String(s || '');
  const words = text.split(/\s+/);
  const w = words[0] || '';
  const core = w.replace(/[^\w'’-]/g, '');
  const bare = core.replace(/['’]s$/, '');
  if (['a', 'an', 'the'].includes(bare.toLowerCase())) return text.charAt(0).toLowerCase() + text.slice(1);
  const second = (words[1] || '').replace(/[^\w'’-]/g, '');
  // A capitalised second word makes a two-word name ("Hong Kong"), unless it's an acronym ("Cheaper AI chips").
  if (/[A-Z0-9]/.test(core.slice(1)) || bare !== core || (/^[A-Z]/.test(second) && !/^[A-Z0-9]{2}/.test(second))
      || PROPER.has(bare.toLowerCase()) || /(ian|ese)$/.test(bare)) return text;
  return text.charAt(0).toLowerCase() + text.slice(1);
}

/** The other side of a hunch: "Bitcoin may slide" -> "I don't think Bitcoin will slide";
 *  "AI firms will pay" -> "I don't think AI firms will pay"; an already negative hunch ("X won't ...") becomes
 *  "I doubt that X won't ..." instead of a double "don't ... won't". */
export function oppositeOf(hunch) {
  const h = String(hunch || '').trim().replace(/[.!]+$/, '');
  if (!h) return '';
  if (NEGATED.test(h)) return `I doubt that ${lowerFirst(h)}`;
  return `I don't think ${lowerFirst(h).replace(/\b(may|might|could)\b/, 'will')}`;
}
