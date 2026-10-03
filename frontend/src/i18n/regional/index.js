/**
 * Regional-language UI catalogs (flat "a.b.c": value files, one per language).
 * en.flat.json is the English source used to produce them; keys missing from a language fall
 * back to English through t(). Proper nouns and units (IMD, JTWC, INSAT-3DS, km/h, hPa) stay as is.
 */
import ta from './ta.json';
import te from './te.json';
import ml from './ml.json';
import bn from './bn.json';
import or from './or.json';
import kn from './kn.json';
import mr from './mr.json';

function unflatten(flat) {
  const out = {};
  for (const [path, value] of Object.entries(flat)) {
    const keys = path.split('.');
    let node = out;
    keys.slice(0, -1).forEach(k => { node[k] = node[k] && typeof node[k] === 'object' ? node[k] : {}; node = node[k]; });
    node[keys[keys.length - 1]] = value;
  }
  return out;
}

export const STRINGS_REGIONAL = Object.fromEntries(
  Object.entries({ ta, te, ml, bn, or, kn, mr }).map(([lang, flat]) => [lang, unflatten(flat)]),
);
