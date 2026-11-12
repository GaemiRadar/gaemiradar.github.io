/* GAEMI RADAR — consent-first Google Analytics 4, no Google tag before consent. */
(function () {
  'use strict';
  const measurementId = window.GAEMI_GA4_MEASUREMENT_ID;
  if (!/^G-[A-Z0-9]{6,20}$/.test(measurementId || '')) return;
  const key = 'gaemi_analytics_consent_v1';
  let tracking = false;
  let banner;

  function getChoice() {
    try { return window.localStorage.getItem(key); }
    catch (_error) { return null; }
  }
  function setChoice(value) {
    try { window.localStorage.setItem(key, value); }
    catch (_error) { /* Private browsing: consent applies only to this page view. */ }
  }
  function sendEvent(name, params) {
    if (tracking && typeof window.gtag === 'function') {
      window.gtag('event', name, params);
    }
  }
  function startTracking() {
    if (tracking) return;
    tracking = true;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag('consent', 'default', {
      analytics_storage: 'denied',
      ad_storage: 'denied',
      ad_user_data: 'denied',
      ad_personalization: 'denied'
    });
    window.gtag('consent', 'update', {
      analytics_storage: 'granted',
      ad_storage: 'denied',
      ad_user_data: 'denied',
      ad_personalization: 'denied'
    });
    window.gtag('js', new Date());
    window.gtag('config', measurementId, { send_page_view: true });
    const script = document.createElement('script');
    script.async = true;
    script.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(measurementId);
    document.head.appendChild(script);
  }
  function eraseAnalyticsCookies() {
    document.cookie.split(';').forEach(function (part) {
      const name = part.split('=')[0].trim();
      if (name === '_ga' || name.indexOf('_ga_') === 0) {
        document.cookie = name + '=; Path=/; Max-Age=0; SameSite=Lax';
      }
    });
  }
  function hideBanner() {
    if (banner) banner.hidden = true;
  }
  function accept() {
    setChoice('granted');
    hideBanner();
    startTracking();
  }
  function reject() {
    setChoice('denied');
    hideBanner();
    eraseAnalyticsCookies();
    if (tracking) {
      if (typeof window.gtag === 'function') {
        window.gtag('consent', 'update', {
          analytics_storage: 'denied', ad_storage: 'denied',
          ad_user_data: 'denied', ad_personalization: 'denied'
        });
      }
      window.location.reload(); // Ensure previously loaded Google scripts stop on the new page.
    }
  }
  function buildUI() {
    const css = document.createElement('style');
    css.textContent =
      '#ga4-consent-banner{position:fixed;z-index:9999;left:16px;right:16px;bottom:16px;max-width:780px;margin:auto;' +
      'padding:19px 20px;background:#101b30;color:#f5f7fe;border:1px solid #52617b;border-radius:16px;' +
      'box-shadow:0 14px 40px rgba(0,0,0,.24);font:14px/1.6 system-ui,sans-serif}' +
      '#ga4-consent-banner[hidden]{display:none!important}' +
      '#ga4-consent-banner strong{font-size:16px}' +
      '#ga4-consent-banner p{margin:7px 0 14px;color:#d8e1ed}' +
      '#ga4-consent-banner a{color:#b7ccff;text-decoration:underline}' +
      '#ga4-consent-banner .ga4-buttons{display:flex;flex-wrap:wrap;gap:10px}' +
      '#ga4-consent-banner button{border:1px solid #99a8c6;border-radius:9px;padding:9px 16px;' +
      'background:#253550;color:#fff;font-weight:700;cursor:pointer}' +
      '#ga4-consent-banner button.ga4-allow{background:#4f63e9;border-color:#4f63e9}' +
      '.ga4-footer-link,.ga4-footer-button{color:inherit;font:inherit;font-size:12px}' +
      '.ga4-footer-button{background:none;border:0;text-decoration:underline;cursor:pointer;padding:0 6px}';
    document.head.appendChild(css);

    banner = document.createElement('section');
    banner.id = 'ga4-consent-banner';
    banner.setAttribute('role', 'region');
    banner.setAttribute('aria-label', '방문 통계 수집 선택');
    banner.hidden = true;
    banner.innerHTML = '<strong>방문 통계 수집 선택</strong>' +
      '<p>개미레이더는 방문자 수·방문 국가·유입 경로·메뉴 클릭을 분석하기 위해 Google Analytics 4를 사용합니다. ' +
      '동의한 경우에만 Google 통계 태그가 로드됩니다. 거부해도 사이트를 이용할 수 있습니다. ' +
      '<a href="./privacy.html">개인정보 처리 안내</a></p>' +
      '<div class="ga4-buttons"><button type="button" class="ga4-allow" id="ga4-accept">통계 수집 동의</button>' +
      '<button type="button" id="ga4-reject">동의하지 않음</button></div>';
    document.body.appendChild(banner);
    document.getElementById('ga4-accept').addEventListener('click', accept);
    document.getElementById('ga4-reject').addEventListener('click', reject);

    const manage = document.getElementById('ga4-manage-consent');
    if (manage) {
      manage.addEventListener('click', function () {
        banner.hidden = false;
        document.getElementById('ga4-accept').focus();
      });
    }
  }

  document.addEventListener('click', function (event) {
    if (!tracking || !(event.target instanceof Element)) return;
    const menu = event.target.closest('[data-tab]');
    if (menu) {
      sendEvent('menu_select', {
        menu_id: menu.getAttribute('data-tab'),
        menu_label: menu.getAttribute('title') || menu.textContent.trim().slice(0, 60)
      });
    }
    const market = event.target.closest('[data-stock-market]');
    if (market) {
      sendEvent('market_select', { market_id: market.getAttribute('data-stock-market') });
    }
  }, true);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, { once: true });
  } else {
    initialize();
  }
  function initialize() {
    buildUI();
    const choice = getChoice();
    if (choice === 'granted') startTracking();
    else if (choice !== 'denied') banner.hidden = false;
  }
})();
