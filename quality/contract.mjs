export const BASE_URL = process.env.QUALITY_BASE_URL || 'http://127.0.0.1:8000';
export const LOCALES = ['fa', 'en', 'de'];
export const SURFACES = [
  { id: 'V-01', name: 'Home', path: '/', a11y: 'full', perf: 'full', seo: 'full', i18n: 'full', indexability: 'public' },
  { id: 'V-02', name: 'Discover root', path: '/discover/', a11y: 'full', perf: 'full', seo: 'full', i18n: 'full', indexability: 'public' },
  { id: 'V-03', name: 'Discover Knowledge', path: '/discover/knowledge/', a11y: 'smoke', perf: 'sample', seo: 'full', i18n: 'full', indexability: 'public' },
  { id: 'V-04', name: 'Discover Media', path: '/discover/media/', a11y: 'smoke', perf: 'sample', seo: 'full', i18n: 'full', indexability: 'public' },
  { id: 'V-05', name: 'Discover Software & Services', path: '/discover/software-services/', a11y: 'smoke', perf: 'sample', seo: 'full', i18n: 'full', indexability: 'public' },
  { id: 'V-06', name: 'Discover Products & Commerce', path: '/discover/products-commerce/', a11y: 'smoke', perf: 'sample', seo: 'full', i18n: 'full', indexability: 'public' },
  { id: 'V-07', name: 'Search', path: '/search/', a11y: 'full', perf: 'full', seo: 'full', i18n: 'full', indexability: 'public' },
  { id: 'V-08', name: 'Marketplace entry', path: '/marketplace/', a11y: 'full', perf: 'full', seo: 'full', i18n: 'full', indexability: 'public' },
  { id: 'V-09', name: 'Login entry', path: '/accounts/login/', a11y: 'full', perf: 'sample', seo: 'policy-check', i18n: 'full', indexability: 'unknown' },
  { id: 'V-10', name: 'Signup entry', path: '/accounts/signup/', a11y: 'full', perf: 'sample', seo: 'policy-check', i18n: 'full', indexability: 'unknown' }
];

export const PERF_THRESHOLDS = {
  lcpMs: 2500,
  cls: 0.10,
  lighthousePerformance: 0.90,
  regression: { lcpPercent: 10, lcpAbsoluteMs: 250, clsAbsolute: 0.02 },
  inp: { targetMs: 200, classification: 'blocked/unknown — insufficient field data' }
};

export const PROFILES = {
  mobile: {
    formFactor: 'mobile',
    screenEmulation: { mobile: true, width: 390, height: 844, deviceScaleFactor: 1, disabled: false },
    throttling: { rttMs: 150, throughputKbps: 1638.4, cpuSlowdownMultiplier: 4, requestLatencyMs: 150, downloadThroughputKbps: 1638.4, uploadThroughputKbps: 675 }
  },
  desktop: {
    formFactor: 'desktop',
    screenEmulation: { mobile: false, width: 1440, height: 900, deviceScaleFactor: 1, disabled: false },
    throttling: { rttMs: 40, throughputKbps: 10240, cpuSlowdownMultiplier: 1, requestLatencyMs: 0, downloadThroughputKbps: 0, uploadThroughputKbps: 0 }
  }
};

export function localizedUrl(locale, path) {
  return `${BASE_URL}/${locale}${path}`.replace(/([^:]\/)\/+/g, '$1');
}
