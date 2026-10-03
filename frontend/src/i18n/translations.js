import { STRINGS_V4, mergeStrings } from './strings_v4';
import { STRINGS_SITE } from './strings_site';
import { STRINGS_STORM } from './strings_storm';
import { STRINGS_REGIONAL } from './regional';

const translations = {
  en: {
    brand: 'Cyclo-Nexus', tagline: 'AI for Safer Coasts', motto: '"Data today. Safer tomorrows."',
    nav: { dashboard: 'Dashboard', liveMonitoring: 'Live Monitoring', cycloneTracking: 'Cyclone Tracking', forecast: 'Forecast & Models', historical: 'Historical Data', alerts: 'Alerts', reports: 'Reports', settings: 'Settings' },
    stats: { activeCyclones: 'Active Cyclones', regionsAtRisk: 'Regions at Risk', peopleAffected: 'People Potentially Affected', modelAccuracy: 'Model Accuracy', fromLastWeek: 'from last week', across: 'Across', states: 'states', last30: 'Last 30 days' },
    map: { satellite: 'Live Satellite', predictedTrack: 'Predicted Track', windFlow: 'Wind Flow', rainfall: 'Rainfall', seaTemp: 'Sea Surface Temperature', currentPos: 'Current Position', forecastTrack: 'Forecast Track', forecastCone: 'Forecast Cone', liveData: 'Live Data', lastUpdated: 'Last updated' },
    panel: { live: 'LIVE', location: 'Location', windSpeed: 'Wind Speed', pressure: 'Central Pressure', movement: 'Movement', nextLandfall: 'Next Landfall', lastUpdated: 'Last Updated', affectedAreas: 'Affected Areas', detailedForecast: 'View Detailed Forecast', share: 'Share' },
    alert: { highRisk: 'High Risk Alert', alertText: 'Heavy rainfall and strong winds expected in coastal regions in next 24-48 hours.' },
    forecast: { title: 'Predicted Track (Next 72 Hours)', viewTable: 'View Table', current: 'Current', hours: 'hours' },
    intensity: { title: 'Intensity Forecast', windSpeedKmh: 'Wind Speed (km/h)', peak: 'Peak', category: 'Category', pressureLabel: 'Pressure', windLabel: 'Wind Speed' },
    env: { title: 'Environmental Conditions', viewMore: 'View More', sst: 'Sea Surface Temperature', humidity: 'Relative Humidity', atmosphericPressure: 'Atmospheric Pressure', rainfall: 'Rainfall (24h)', surfaceWinds: 'Surface Winds' },
    footer: { ministry: 'Ministry of Earth Sciences', govIndia: 'Government of India', isro: 'ISRO', isroSub: 'Satellite Data', imd: 'IMD', imdSub: 'Weather Observations', incois: 'INCOIS', incoisSub: 'Ocean Information', ndma: 'NDMA', ndmaSub: 'Disaster Preparedness' },
    search: 'Search location, cyclone, or date...', earlyWarnings: 'Early Warnings Save Lives', noData: 'No Active Cyclones', noDataSub: 'The system is monitoring. Data will appear when a cyclone is detected.',
  },
  hi: {
    brand: 'Cyclo-Nexus', tagline: 'सुरक्षित तटों के लिए AI', motto: '"आज का डेटा। सुरक्षित कल।"',
    nav: { dashboard: 'डैशबोर्ड', liveMonitoring: 'लाइव निगरानी', cycloneTracking: 'चक्रवात ट्रैकिंग', forecast: 'पूर्वानुमान', historical: 'ऐतिहासिक डेटा', alerts: 'अलर्ट', reports: 'रिपोर्ट', settings: 'सेटिंग्स' },
    stats: { activeCyclones: 'सक्रिय चक्रवात', regionsAtRisk: 'जोखिम वाले क्षेत्र', peopleAffected: 'प्रभावित जनसंख्या', modelAccuracy: 'मॉडल सटीकता', fromLastWeek: 'पिछले सप्ताह से', across: '', states: 'राज्यों में', last30: 'पिछले 30 दिन' },
    map: { satellite: 'लाइव उपग्रह', predictedTrack: 'अनुमानित मार्ग', windFlow: 'हवा प्रवाह', rainfall: 'वर्षा', seaTemp: 'समुद्र सतह तापमान', currentPos: 'वर्तमान स्थिति', forecastTrack: 'पूर्वानुमान मार्ग', forecastCone: 'पूर्वानुमान शंकु', liveData: 'लाइव डेटा', lastUpdated: 'अंतिम अपडेट' },
    panel: { live: 'लाइव', location: 'स्थान', windSpeed: 'हवा गति', pressure: 'केंद्रीय दबाव', movement: 'गति', nextLandfall: 'अगला लैंडफॉल', lastUpdated: 'अंतिम अपडेट', affectedAreas: 'प्रभावित क्षेत्र', detailedForecast: 'विस्तृत पूर्वानुमान', share: 'शेयर' },
    alert: { highRisk: 'उच्च जोखिम चेतावनी', alertText: 'तटीय क्षेत्रों में अगले 24-48 घंटों में भारी बारिश और तेज़ हवाओं की उम्मीद।' },
    forecast: { title: 'अनुमानित मार्ग (अगले 72 घंटे)', viewTable: 'तालिका देखें', current: 'वर्तमान', hours: 'घंटे' },
    intensity: { title: 'तीव्रता पूर्वानुमान', windSpeedKmh: 'हवा गति (किमी/घंटा)', peak: 'शिखर', category: 'श्रेणी', pressureLabel: 'दबाव', windLabel: 'हवा गति' },
    env: { title: 'पर्यावरणीय स्थिति', viewMore: 'और देखें', sst: 'समुद्र सतह तापमान', humidity: 'सापेक्ष आर्द्रता', atmosphericPressure: 'वायुमंडलीय दबाव', rainfall: 'वर्षा (24घंटे)', surfaceWinds: 'सतही हवाएं' },
    footer: { ministry: 'पृथ्वी विज्ञान मंत्रालय', govIndia: 'भारत सरकार' },
    search: 'स्थान, चक्रवात या तारीख खोजें...', earlyWarnings: 'पूर्व चेतावनी जीवन बचाती है', noData: 'कोई सक्रिय चक्रवात नहीं', noDataSub: 'सिस्टम निगरानी कर रहा है।',
  },
  ta: {
    brand: 'Cyclo-Nexus', tagline: 'பாதுகாப்பான கடற்கரைகளுக்கு AI', motto: '"இன்றைய தரவு. நாளைய பாதுகாப்பு."',
    nav: { dashboard: 'டாஷ்போர்டு', liveMonitoring: 'நேரடி கண்காணிப்பு', cycloneTracking: 'புயல் கண்காணிப்பு', forecast: 'முன்னறிவிப்பு', historical: 'வரலாற்று தரவு', alerts: 'எச்சரிக்கைகள்', reports: 'அறிக்கைகள்', settings: 'அமைப்புகள்' },
    stats: { activeCyclones: 'செயலில் புயல்கள்', regionsAtRisk: 'ஆபத்து பகுதிகள்', peopleAffected: 'பாதிக்கப்பட்ட மக்கள்', modelAccuracy: 'மாதிரி துல்லியம்', fromLastWeek: 'கடந்த வாரத்திலிருந்து', across: '', states: 'மாநிலங்களில்', last30: 'கடந்த 30 நாட்கள்' },
    search: 'இடம், புயல் அல்லது தேதியை தேடுங்கள்...', earlyWarnings: 'முன் எச்சரிக்கை உயிர்களைக் காக்கிறது', noData: 'செயலில் புயல்கள் இல்லை', noDataSub: 'கணினி கண்காணிக்கிறது.',
    alert: { highRisk: 'உயர் ஆபத்து எச்சரிக்கை', alertText: 'கடலோர பகுதிகளில் அடுத்த 24-48 மணி நேரத்தில் கனமழை எதிர்பார்க்கப்படுகிறது.' },
  },
  te: {
    brand: 'Cyclo-Nexus', tagline: 'సురక్షిత తీరాలకు AI', motto: '"నేటి డేటా. రేపటి భద్రత."',
    nav: { dashboard: 'డాష్‌బోర్డ్', liveMonitoring: 'లైవ్ మానిటరింగ్', cycloneTracking: 'తుఫాను ట్రాకింగ్', forecast: 'అంచనా', historical: 'చారిత్రక డేటా', alerts: 'హెచ్చరికలు', reports: 'నివేదికలు', settings: 'సెట్టింగ్‌లు' },
    stats: { activeCyclones: 'యాక్టివ్ తుఫానులు', regionsAtRisk: 'ప్రమాద ప్రాంతాలు', peopleAffected: 'ప్రభావిత జనాభా', modelAccuracy: 'మోడల్ ఖచ్చితత్వం' },
    search: 'స్థలం, తుఫాను లేదా తేదీ శోధించండి...', noData: 'యాక్టివ్ తుఫానులు లేవు', noDataSub: 'సిస్టమ్ పర్యవేక్షిస్తోంది.',
    alert: { highRisk: 'అధిక ప్రమాద హెచ్చరిక', alertText: 'తీర ప్రాంతాల్లో 24-48 గంటల్లో భారీ వర్షం ఆశించబడుతోంది.' },
  },
  ml: {
    brand: 'Cyclo-Nexus', tagline: 'സുരക്ഷിത തീരങ്ങൾക്കായി AI',
    nav: { dashboard: 'ഡാഷ്‌ബോർഡ്', liveMonitoring: 'തത്സമയ നിരീക്ഷണം', cycloneTracking: 'ചുഴലിക്കാറ്റ് ട്രാക്കിംഗ്', forecast: 'പ്രവചനം', alerts: 'മുന്നറിയിപ്പുകൾ', settings: 'ക്രമീകരണങ്ങൾ' },
    stats: { activeCyclones: 'സജീവ ചുഴലിക്കാറ്റുകൾ', regionsAtRisk: 'അപകട മേഖലകൾ', peopleAffected: 'ബാധിത ജനം', modelAccuracy: 'മോഡൽ കൃത്യത' },
    search: 'സ്ഥലം, ചുഴലിക്കാറ്റ് തിരയുക...', noData: 'സജീവ ചുഴലിക്കാറ്റുകൾ ഇല്ല',
  },
  bn: {
    brand: 'Cyclo-Nexus', tagline: 'নিরাপদ উপকূলের জন্য AI',
    nav: { dashboard: 'ড্যাশবোর্ড', liveMonitoring: 'লাইভ মনিটরিং', cycloneTracking: 'ঘূর্ণিঝড় ট্র্যাকিং', forecast: 'পূর্বাভাস', alerts: 'সতর্কতা', settings: 'সেটিংস' },
    stats: { activeCyclones: 'সক্রিয় ঘূর্ণিঝড়', regionsAtRisk: 'ঝুঁকিপূর্ণ অঞ্চল', peopleAffected: 'আক্রান্ত জনসংখ্যা', modelAccuracy: 'মডেল নির্ভুলতা' },
    search: 'অবস্থান, ঘূর্ণিঝড় বা তারিখ অনুসন্ধান করুন...', noData: 'কোনো সক্রিয় ঘূর্ণিঝড় নেই',
  },
  or: {
    brand: 'Cyclo-Nexus', tagline: 'ସୁରକ୍ଷିତ ଉପକୂଳ ପାଇଁ AI',
    nav: { dashboard: 'ଡ୍ୟାସବୋର୍ଡ', alerts: 'ସତର୍କତା' },
    stats: { activeCyclones: 'ସକ୍ରିୟ ଚକ୍ରବାତ', regionsAtRisk: 'ବିପଦ ଅଞ୍ଚଳ', peopleAffected: 'ପ୍ରଭାବିତ ଲୋକ', modelAccuracy: 'ମଡେଲ ସଠିକତା' },
    search: 'ଅବସ୍ଥାନ, ଚକ୍ରବାତ ଖୋଜନ୍ତୁ...', noData: 'କୌଣସି ସକ୍ରିୟ ଚକ୍ରବାତ ନାହିଁ',
  },
  kn: {
    brand: 'Cyclo-Nexus', tagline: 'ಸುರಕ್ಷಿತ ಕರಾವಳಿಗಳಿಗಾಗಿ AI',
    nav: { dashboard: 'ಡ್ಯಾಶ್‌ಬೋರ್ಡ್', alerts: 'ಎಚ್ಚರಿಕೆಗಳು' },
    stats: { activeCyclones: 'ಸಕ್ರಿಯ ಚಂಡಮಾರುತಗಳು', regionsAtRisk: 'ಅಪಾಯ ಪ್ರದೇಶಗಳು' },
    search: 'ಸ್ಥಳ, ಚಂಡಮಾರುತ ಹುಡುಕಿ...', noData: 'ಸಕ್ರಿಯ ಚಂಡಮಾರುತಗಳಿಲ್ಲ',
  },
  mr: {
    brand: 'Cyclo-Nexus', tagline: 'सुरक्षित किनाऱ्यांसाठी AI',
    nav: { dashboard: 'डॅशबोर्ड', alerts: 'सूचना' },
    stats: { activeCyclones: 'सक्रिय चक्रीवादळे', regionsAtRisk: 'धोकादायक क्षेत्रे' },
    search: 'स्थान, चक्रीवादळ शोधा...', noData: 'सक्रिय चक्रीवादळे नाहीत',
  },
};

// v4 strings (official vs satellite layers, new pages)
mergeStrings(translations, STRINGS_V4);
mergeStrings(translations, STRINGS_SITE);
mergeStrings(translations, STRINGS_STORM);
mergeStrings(translations, STRINGS_REGIONAL);

// Deep merge helper: falls back to English for missing keys
function deepGet(obj, path, fallback) {
  const keys = path.split('.');
  let result = obj;
  for (const key of keys) {
    if (result && typeof result === 'object' && key in result) {
      result = result[key];
    } else {
      return fallback;
    }
  }
  return result;
}

export function t(lang, path) {
  const val = deepGet(translations[lang], path);
  if (val !== undefined) return val;
  return deepGet(translations.en, path) || path;
}

export const LANGUAGES = [
  { code: 'en', label: 'English', native: 'English' },
  { code: 'hi', label: 'Hindi', native: 'हिन्दी' },
  { code: 'ta', label: 'Tamil', native: 'தமிழ்' },
  { code: 'te', label: 'Telugu', native: 'తెలుగు' },
  { code: 'ml', label: 'Malayalam', native: 'മലയാളം' },
  { code: 'bn', label: 'Bengali', native: 'বাংলা' },
  { code: 'or', label: 'Odia', native: 'ଓଡ଼ିଆ' },
  { code: 'kn', label: 'Kannada', native: 'ಕನ್ನಡ' },
  { code: 'mr', label: 'Marathi', native: 'मराठी' },
];

export default translations;
