/**
 * Template Advisory Generator
 * ═══════════════════════════
 * Master plan v4 (replaces the Gemini stub — user chose deterministic templates).
 *
 * Builds public advisories only from numbers already in the database, so nothing can be
 * invented. Alert levels follow schemas/imd_scale.py ALERT_THRESHOLDS_KMH:
 *   RED ≥ 118 km/h (VSCS+), ORANGE ≥ 62 km/h (CS/SCS), YELLOW ≥ 31 km/h (D/DD).
 * Satellite watch areas get an informational notice, never an alert level.
 *
 * Languages: en, hi. Other UI languages receive English with `fallback: true`
 * (safety text should be reviewed by native speakers before adding more).
 */

const CATEGORY_NAMES = {
  en: {
    D: 'Depression', DD: 'Deep Depression', CS: 'Cyclonic Storm', SCS: 'Severe Cyclonic Storm',
    VSCS: 'Very Severe Cyclonic Storm', ESCS: 'Extremely Severe Cyclonic Storm', SuCS: 'Super Cyclonic Storm',
  },
  hi: {
    D: 'अवदाब', DD: 'गहरा अवदाब', CS: 'चक्रवाती तूफान', SCS: 'गंभीर चक्रवाती तूफान',
    VSCS: 'अति गंभीर चक्रवाती तूफान', ESCS: 'अत्यंत गंभीर चक्रवाती तूफान', SuCS: 'महा चक्रवाती तूफान',
  },
};

const SEA = { en: { BOB: 'Bay of Bengal', AS: 'Arabian Sea', NIO: 'North Indian Ocean' },
  hi: { BOB: 'बंगाल की खाड़ी', AS: 'अरब सागर', NIO: 'उत्तर हिंद महासागर' } };

const TEXT = {
  en: {
    summary: (c, cat, sea) => `${c.name ? `${cat} "${c.name}"` : `A ${cat.toLowerCase()}`} is located over the ${sea} near `
      + `${c.lat}°N, ${c.lon}°E with maximum sustained winds of about ${c.wind} km/h and central pressure near ${c.pressure} hPa`
      + ` (observed ${c.time} UTC).`,
    movement: m => ` It moved ${m.dir} at about ${m.speed} km/h over the last ${m.hours} hours.`,
    watch: (c, sea) => `Satellites show an area of organised deep convection over the ${sea} near ${c.lat}°N, ${c.lon}°E `
      + `(observed ${c.time} UTC). It is being monitored for possible development. This is not an official warning.`,
    fishermen: {
      YELLOW: sea => `Fishermen are advised to exercise caution in the ${sea} and follow IMD bulletins.`,
      ORANGE: sea => `Fishermen are advised not to venture into the ${sea}. Those at sea should return to the coast.`,
      RED: sea => `Total suspension of fishing operations in the ${sea}. Those at sea must return to the coast immediately.`,
    },
    public: {
      YELLOW: 'Stay updated with IMD and your State Disaster Management Authority. Expect rain and gusty winds along nearby coasts.',
      ORANGE: 'Coastal residents should secure loose objects, keep emergency kits ready and follow local authority instructions.',
      RED: 'Follow evacuation orders from local authorities immediately. Move to designated cyclone shelters if advised.',
    },
    administration: {
      YELLOW: 'Monitor official bulletins; review preparedness of coastal districts.',
      ORANGE: 'Activate district emergency operation centres; prepare shelters and communication.',
      RED: 'Execute evacuation of vulnerable coastal areas; pre-position rescue and relief teams.',
    },
    disclaimer: 'Auto-generated from JTWC / IBTrACS data by Cyclo-Nexus. The official authority for India is the India '
      + 'Meteorological Department (mausam.imd.gov.in); always follow IMD and State Disaster Management Authority instructions.',
  },
  hi: {
    summary: (c, cat, sea) => `${c.name ? `${cat} "${c.name}"` : cat} ${sea} पर ${c.lat}°उ, ${c.lon}°पू के निकट स्थित है। `
      + `अधिकतम निरंतर हवा लगभग ${c.wind} किमी/घंटा और केंद्रीय दाब लगभग ${c.pressure} हेक्टोपास्कल है (अवलोकन ${c.time} UTC)।`,
    movement: m => ` पिछले ${m.hours} घंटों में यह लगभग ${m.speed} किमी/घंटा की गति से ${m.dirHi} दिशा में बढ़ा है।`,
    watch: (c, sea) => `उपग्रह ${sea} पर ${c.lat}°उ, ${c.lon}°पू के निकट संगठित गहरे संवहन का क्षेत्र दिखा रहे हैं `
      + `(अवलोकन ${c.time} UTC)। संभावित विकास के लिए इसकी निगरानी की जा रही है। यह आधिकारिक चेतावनी नहीं है।`,
    fishermen: {
      YELLOW: sea => `मछुआरों को ${sea} में सावधानी बरतने और IMD बुलेटिन का पालन करने की सलाह दी जाती है।`,
      ORANGE: sea => `मछुआरों को ${sea} में न जाने की सलाह दी जाती है। समुद्र में मौजूद लोग तट पर लौट आएँ।`,
      RED: sea => `${sea} में मछली पकड़ने का कार्य पूरी तरह बंद रहेगा। समुद्र में मौजूद लोग तुरंत तट पर लौटें।`,
    },
    public: {
      YELLOW: 'IMD और राज्य आपदा प्रबंधन प्राधिकरण की जानकारी देखते रहें। निकटवर्ती तटों पर वर्षा और तेज़ हवाएँ संभव हैं।',
      ORANGE: 'तटीय निवासी ढीली वस्तुएँ सुरक्षित करें, आपातकालीन किट तैयार रखें और स्थानीय प्रशासन के निर्देशों का पालन करें।',
      RED: 'स्थानीय प्रशासन के निकासी आदेशों का तुरंत पालन करें। सलाह दिए जाने पर निर्धारित चक्रवात आश्रयों में जाएँ।',
    },
    administration: {
      YELLOW: 'आधिकारिक बुलेटिनों की निगरानी करें; तटीय जिलों की तैयारी की समीक्षा करें।',
      ORANGE: 'जिला आपातकालीन संचालन केंद्र सक्रिय करें; आश्रय स्थल और संचार व्यवस्था तैयार रखें।',
      RED: 'संवेदनशील तटीय क्षेत्रों से निकासी करें; बचाव और राहत दल पहले से तैनात करें।',
    },
    disclaimer: 'यह परामर्श Cyclo-Nexus द्वारा JTWC / IBTrACS आंकड़ों से स्वतः तैयार किया गया है। भारत के लिए आधिकारिक '
      + 'प्राधिकरण भारत मौसम विज्ञान विभाग (mausam.imd.gov.in) है; हमेशा IMD और राज्य आपदा प्रबंधन प्राधिकरण के निर्देशों का पालन करें।',
  },
};

const DIRS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
const DIRS_HI = ['उत्तर', 'उत्तर-उत्तरपूर्व', 'उत्तरपूर्व', 'पूर्व-उत्तरपूर्व', 'पूर्व', 'पूर्व-दक्षिणपूर्व', 'दक्षिणपूर्व', 'दक्षिण-दक्षिणपूर्व',
  'दक्षिण', 'दक्षिण-दक्षिणपश्चिम', 'दक्षिणपश्चिम', 'पश्चिम-दक्षिणपश्चिम', 'पश्चिम', 'पश्चिम-उत्तरपश्चिम', 'उत्तरपश्चिम', 'उत्तर-उत्तरपश्चिम'];

/** Movement from the last two observed positions at least 3 h apart. */
function computeMovement(history) {
  if (!history || history.length < 2) return null;
  const last = history[history.length - 1];
  const tLast = new Date(last.timestamp).getTime();
  const prev = [...history].reverse().find(h => tLast - new Date(h.timestamp).getTime() >= 3 * 3600e3);
  if (!prev) return null;
  const hours = (tLast - new Date(prev.timestamp).getTime()) / 3600e3;
  const toRad = d => (d * Math.PI) / 180;
  const lat1 = toRad(Number(prev.latitude)); const lat2 = toRad(Number(last.latitude));
  const dLon = toRad(Number(last.longitude) - Number(prev.longitude));
  const dist = 6371 * 2 * Math.asin(Math.sqrt(Math.sin((lat2 - lat1) / 2) ** 2
    + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2));
  const bearing = (Math.atan2(Math.sin(dLon) * Math.cos(lat2),
    Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon)) * 180 / Math.PI + 360) % 360;
  const idx = Math.round(bearing / 22.5) % 16;
  return {
    bearing_deg: Math.round(bearing), dir: DIRS[idx], dirHi: DIRS_HI[idx],
    speed: Math.round(dist / hours), hours: Math.round(hours),
  };
}

function alertLevel(windKmh) {
  if (windKmh >= 118) return 'RED';
  if (windKmh >= 62) return 'ORANGE';
  if (windKmh >= 31) return 'YELLOW';
  return null;
}

function buildAdvisory(cyclone, lang = 'en') {
  const language = TEXT[lang] ? lang : 'en';
  const T = TEXT[language];
  const sea = SEA[language][cyclone.basin] || SEA[language].NIO;
  const fmtTime = new Date(cyclone.observation_time).toISOString().slice(0, 16).replace('T', ' ');
  const c = {
    name: cyclone.cyclone_name,
    lat: Number(cyclone.current_lat).toFixed(1),
    lon: Number(cyclone.current_lon).toFixed(1),
    wind: Math.round(Number(cyclone.sustained_wind_kmh)),
    pressure: Math.round(Number(cyclone.central_pressure_hpa)),
    time: fmtTime,
  };
  const movement = computeMovement(cyclone.history);
  const isOfficial = String(cyclone.source || '').startsWith('OFFICIAL_');
  const base = {
    cyclone_id: cyclone.cyclone_id, language, fallback: language !== lang, source: cyclone.source,
    source_url: cyclone.source_url || null, observation_time: cyclone.observation_time, movement,
    disclaimer: T.disclaimer, generated_at: new Date().toISOString(),
  };

  if (!isOfficial || cyclone.status === 'watch') {
    return { ...base, alert_level: null, type: 'watch', threat_summary: T.watch(c, sea),
      directives_fishermen: null, directives_public: null, directives_administration: null };
  }

  const level = alertLevel(Number(cyclone.sustained_wind_kmh)) || 'YELLOW';
  const cat = CATEGORY_NAMES[language][cyclone.imd_category] || cyclone.imd_category;
  return {
    ...base,
    type: 'advisory',
    alert_level: level,
    threat_summary: T.summary(c, cat, sea) + (movement ? T.movement(movement) : ''),
    directives_fishermen: T.fishermen[level](sea),
    directives_public: T.public[level],
    directives_administration: T.administration[level],
  };
}

module.exports = { buildAdvisory, computeMovement, alertLevel, SUPPORTED_LANGUAGES: Object.keys(TEXT) };
