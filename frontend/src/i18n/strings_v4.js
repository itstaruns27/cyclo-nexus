/**
 * UI strings added in master plan v4 (official vs satellite layers, new pages).
 * English and Hindi; other languages fall back to English via t().
 */

export const STRINGS_V4 = {
  en: {
    nav: { dashboard: 'Dashboard', forecast: 'Forecast Tracks', historical: 'Historical Data', alerts: 'Advisories', status: 'System Status' },
    stats: {
      officialSystems: 'Official Systems', watchAreas: 'Satellite Watch Areas', highestAlert: 'Highest Alert',
      dataAge: 'Satellite Data Age', none: 'None', noAlert: 'No alert', officialSub: 'JTWC / IBTrACS',
      watchSub: 'Experimental detector', alertSub: 'From official intensity', ageSub: 'INSAT-3DS + IMERG', unknown: 'Unknown',
    },
    source: { official: 'Official', watch: 'Satellite watch', experimental: 'Experimental' },
    panel: {
      source: 'Source', observed: 'Observed', satellite: 'Satellite analysis (350 km)', coldestTop: 'Coldest cloud top',
      peakRain: 'Peak rain (IMERG)', score: 'Detection score', viewSource: 'Official bulletin',
      noMovement: 'Not enough track history', systems: 'Active systems',
      watchNote: 'Organised deep convection seen by satellite. Not an official warning; position uncertainty about ±300 km.',
      viewAdvisory: 'View advisory', viewForecast: 'View forecast', notReported: 'Not reported',
    },
    banner: {
      stale: 'Some data sources are delayed:', offline: 'Cannot reach the Cyclo-Nexus server — showing the last data received.',
      official_feed: 'official bulletins', satellite_pipeline: 'satellite pipeline',
    },
    env: {
      atCentre: 'Conditions at Centre', provider: 'Open-Meteo, current', pressure: 'Sea-level Pressure',
      rainToday: 'Rain Today', unavailable: 'Unavailable', overLand: 'Over land',
    },
    inspector: {
      title: 'Point Conditions', genesis: 'Cyclogenesis indicators (simplified)', met: 'of 3 conditions met',
      land: 'Over land — tropical cyclones form only over warm ocean.', sst: 'Sea surface temp.', pressure: 'Pressure deficit',
      wind: '10 m wind', loading: 'Fetching conditions…', error: 'Could not load conditions.', note: 'Indicator only, not a forecast.',
    },
    forecastPage: {
      title: 'Forecast Tracks', official: 'Official forecast', ai: 'AI forecast (experimental)', none: 'No forecast track available.',
      hour: 'Lead time', position: 'Position', wind: 'Wind', category: 'Category', valid: 'Valid (UTC)',
      noSystems: 'No official system is active. Forecast tracks appear here when JTWC issues warnings.',
    },
    historicalPage: {
      title: 'Historical Cyclones', subtitle: 'IBTrACS best tracks, North Indian Ocean (RSMC New Delhi values where available)',
      season: 'Season', storms: 'storms', peak: 'Peak grade', maxWind: 'Max wind', minPressure: 'Min pressure',
      select: 'Select a storm to see its track.', unnamed: 'Unnamed', dates: 'Dates', basin: 'Basin', points: 'track points',
    },
    alertsPage: {
      title: 'Advisories', fishermen: 'Fishermen', public: 'Public', administration: 'Administration',
      none: 'No advisories — no official system is active in the North Indian Ocean.', watchTitle: 'Satellite watch notices',
      englishOnly: 'Shown in English (translation not yet reviewed for this language).', loading: 'Loading advisories…',
      capAlert: 'CAP 1.2 alert (XML)', capFeed: 'Machine-readable alert feed (CAP 1.2 / Atom) for SACHET and alert aggregators',
    },
    statusPage: {
      title: 'System Status', component: 'Component', status: 'Status', lastSuccess: 'Last success', lastData: 'Latest data',
      message: 'Details', api: 'API', database: 'Database', sources: 'Data Sources', validation: 'Detector Validation',
      validationText: 'The satellite watch detector is validated against real IBTrACS cases; see docs/validation_report.md in the repository.',
      stale: 'Stale', never: 'Never',
    },
    map: {
      history: 'Observed track', officialTrack: 'Official forecast', cone: 'Forecast cone (IMD track error)', aiTrack: 'AI forecast', watchArea: 'Watch area (±300 km)',
      clickHint: 'Click the ocean to check conditions', offline: 'Offline', delayed: 'Delayed',
    },
    footer: {
      disclaimer: 'Smart India Hackathon project (MoES problem SIH26070). Not an official warning service — always follow IMD.',
      sources: 'Data: ISRO MOSDAC (INSAT-3DS), NASA GPM IMERG & GIBS, JTWC, NOAA IBTrACS, Open-Meteo',
    },
    noDataSub: 'No official system and no satellite watch area in the North Indian Ocean right now.',
    menu: 'Menu',
  },
  hi: {
    nav: { dashboard: 'डैशबोर्ड', forecast: 'पूर्वानुमान मार्ग', historical: 'ऐतिहासिक डेटा', alerts: 'परामर्श', status: 'सिस्टम स्थिति' },
    stats: {
      officialSystems: 'आधिकारिक प्रणालियाँ', watchAreas: 'उपग्रह निगरानी क्षेत्र', highestAlert: 'सर्वोच्च अलर्ट',
      dataAge: 'उपग्रह डेटा की आयु', none: 'कोई नहीं', noAlert: 'कोई अलर्ट नहीं', officialSub: 'JTWC / IBTrACS',
      watchSub: 'प्रायोगिक डिटेक्टर', alertSub: 'आधिकारिक तीव्रता से', ageSub: 'INSAT-3DS + IMERG', unknown: 'अज्ञात',
    },
    source: { official: 'आधिकारिक', watch: 'उपग्रह निगरानी', experimental: 'प्रायोगिक' },
    panel: {
      source: 'स्रोत', observed: 'अवलोकन', satellite: 'उपग्रह विश्लेषण (350 किमी)', coldestTop: 'सबसे ठंडा बादल शीर्ष',
      peakRain: 'अधिकतम वर्षा (IMERG)', score: 'पहचान स्कोर', viewSource: 'आधिकारिक बुलेटिन',
      noMovement: 'पर्याप्त मार्ग इतिहास नहीं', systems: 'सक्रिय प्रणालियाँ',
      watchNote: 'उपग्रह द्वारा देखा गया संगठित गहरा संवहन। यह आधिकारिक चेतावनी नहीं है; स्थिति में लगभग ±300 किमी की अनिश्चितता।',
      viewAdvisory: 'परामर्श देखें', viewForecast: 'पूर्वानुमान देखें', notReported: 'उपलब्ध नहीं',
    },
    banner: {
      stale: 'कुछ डेटा स्रोतों में देरी है:', offline: 'Cyclo-Nexus सर्वर से संपर्क नहीं हो पा रहा — अंतिम प्राप्त डेटा दिखाया जा रहा है।',
      official_feed: 'आधिकारिक बुलेटिन', satellite_pipeline: 'उपग्रह पाइपलाइन',
    },
    env: {
      atCentre: 'केंद्र पर स्थिति', provider: 'Open-Meteo, वर्तमान', pressure: 'समुद्र-स्तर दाब',
      rainToday: 'आज की वर्षा', unavailable: 'उपलब्ध नहीं', overLand: 'भूमि पर',
    },
    inspector: {
      title: 'बिंदु की स्थिति', genesis: 'चक्रवात-उत्पत्ति संकेतक (सरलीकृत)', met: '3 में से शर्तें पूरी',
      land: 'भूमि पर — उष्णकटिबंधीय चक्रवात केवल गर्म समुद्र पर बनते हैं।', sst: 'समुद्र सतह तापमान', pressure: 'दाब की कमी',
      wind: '10 मी हवा', loading: 'स्थिति प्राप्त की जा रही है…', error: 'स्थिति लोड नहीं हो सकी।', note: 'केवल संकेतक, पूर्वानुमान नहीं।',
    },
    forecastPage: {
      title: 'पूर्वानुमान मार्ग', official: 'आधिकारिक पूर्वानुमान', ai: 'AI पूर्वानुमान (प्रायोगिक)', none: 'कोई पूर्वानुमान मार्ग उपलब्ध नहीं।',
      hour: 'समय', position: 'स्थिति', wind: 'हवा', category: 'श्रेणी', valid: 'मान्य (UTC)',
      noSystems: 'कोई आधिकारिक प्रणाली सक्रिय नहीं है। JTWC चेतावनी जारी होने पर मार्ग यहाँ दिखेंगे।',
    },
    historicalPage: {
      title: 'ऐतिहासिक चक्रवात', subtitle: 'IBTrACS बेस्ट ट्रैक, उत्तर हिंद महासागर (जहाँ उपलब्ध हो RSMC नई दिल्ली के मान)',
      season: 'वर्ष', storms: 'तूफान', peak: 'अधिकतम श्रेणी', maxWind: 'अधिकतम हवा', minPressure: 'न्यूनतम दाब',
      select: 'मार्ग देखने के लिए तूफान चुनें।', unnamed: 'अनाम', dates: 'तिथियाँ', basin: 'क्षेत्र', points: 'मार्ग बिंदु',
    },
    alertsPage: {
      title: 'परामर्श', fishermen: 'मछुआरे', public: 'जनता', administration: 'प्रशासन',
      none: 'कोई परामर्श नहीं — उत्तर हिंद महासागर में कोई आधिकारिक प्रणाली सक्रिय नहीं है।', watchTitle: 'उपग्रह निगरानी सूचनाएँ',
      englishOnly: 'अंग्रेज़ी में दिखाया गया है (इस भाषा का अनुवाद अभी समीक्षित नहीं है)।', loading: 'परामर्श लोड हो रहे हैं…',
      capAlert: 'CAP 1.2 चेतावनी (XML)', capFeed: 'SACHET और चेतावनी एग्रीगेटरों के लिए मशीन-पठनीय फ़ीड (CAP 1.2 / Atom)',
    },
    statusPage: {
      title: 'सिस्टम स्थिति', component: 'घटक', status: 'स्थिति', lastSuccess: 'अंतिम सफलता', lastData: 'नवीनतम डेटा',
      message: 'विवरण', api: 'API', database: 'डेटाबेस', sources: 'डेटा स्रोत', validation: 'डिटेक्टर सत्यापन',
      validationText: 'उपग्रह निगरानी डिटेक्टर को वास्तविक IBTrACS मामलों पर सत्यापित किया गया है; रिपॉज़िटरी में docs/validation_report.md देखें।',
      stale: 'पुराना', never: 'कभी नहीं',
    },
    map: {
      history: 'अवलोकित मार्ग', officialTrack: 'आधिकारिक पूर्वानुमान', cone: 'पूर्वानुमान शंकु (IMD मार्ग त्रुटि)', aiTrack: 'AI पूर्वानुमान', watchArea: 'निगरानी क्षेत्र (±300 किमी)',
      clickHint: 'स्थिति देखने के लिए समुद्र पर क्लिक करें', offline: 'ऑफ़लाइन', delayed: 'विलंबित',
    },
    footer: {
      disclaimer: 'स्मार्ट इंडिया हैकथॉन परियोजना (MoES समस्या SIH26070)। यह आधिकारिक चेतावनी सेवा नहीं है — हमेशा IMD का पालन करें।',
      sources: 'डेटा: ISRO MOSDAC (INSAT-3DS), NASA GPM IMERG व GIBS, JTWC, NOAA IBTrACS, Open-Meteo',
    },
    noDataSub: 'इस समय उत्तर हिंद महासागर में कोई आधिकारिक प्रणाली या उपग्रह निगरानी क्षेत्र नहीं है।',
    menu: 'मेनू',
  },
};

/** Deep-merge `extra` into `base` (objects merged, leaves overwritten). */
export function mergeStrings(base, extra) {
  for (const [lang, tree] of Object.entries(extra)) {
    base[lang] = base[lang] || {};
    const walk = (dst, src) => {
      for (const [k, v] of Object.entries(src)) {
        if (v && typeof v === 'object' && !Array.isArray(v)) {
          dst[k] = dst[k] && typeof dst[k] === 'object' ? dst[k] : {};
          walk(dst[k], v);
        } else {
          dst[k] = v;
        }
      }
    };
    walk(base[lang], tree);
  }
}
