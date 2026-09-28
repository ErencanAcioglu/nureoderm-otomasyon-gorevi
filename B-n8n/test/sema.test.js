'use strict';

// workflow.json'ın n8n'in gerçek düğüm tanımlarına (n8n-nodes-base/dist/types/nodes.json) uyumu +
// doğrulayıcının kendisinin hata yakaladığının kanıtı (bilerek bozulmuş kopyalar).
// İlk çalıştırmada paket npm'den indirilir (~9 MB, .cache/); ağ yoksa test atlanır.

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { dogrula, tanimlariYukle } = require('../araclar/sema-dogrula');

let tanimlar = null;
try { tanimlar = tanimlariYukle(); } catch { /* ağ yok → atla */ }
const secenek = { skip: tanimlar ? false : 'n8n-nodes-base tanımları indirilemedi (ağ yok)' };

const temiz = () => JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'workflow.json'), 'utf8'));
const dugum = (w, ad) => w.nodes.find((n) => n.name === ad);
const HTTP = 'Laptop Sayfalarını Çek (Sayfalama)';
const OKU = 'Önceki Durumu Oku (son_durum)';
const hatalar = (w) => {
  const { rapor, baglantiHatalari } = dogrula(w, tanimlar);
  return rapor.flatMap((r) => r.hatalar).concat(baglantiHatalari);
};

test('workflow.json: 19/19 düğüm n8n tanımlarına uygun, 0 hata', secenek, () => {
  assert.deepEqual(hatalar(temiz()), []);
});

const MUTASYONLAR = {
  'Sheets operation=getAll': [(w) => { dugum(w, OKU).parameters.operation = 'getAll'; }, /geçersiz değer "getAll"/],
  'sayfalama parametresinde yazım hatası': [(w) => {
    const p = dugum(w, HTTP).parameters.options.pagination.pagination;
    p.maxRequest = p.maxRequests; delete p.maxRequests;
  }, /maxRequest: bilinmeyen parametre/],
  'geçersiz responseFormat': [(w) => { dugum(w, HTTP).parameters.options.response.response.responseFormat = 'html'; }, /geçersiz değer "html"/],
  'displayOptions: json yanıtta outputPropertyName görünmez': [(w) => {
    dugum(w, HTTP).parameters.options.response.response.responseFormat = 'json';
  }, /outputPropertyName: bu ayarlarla görünmüyor/],
  'olmayan typeVersion': [(w) => { dugum(w, HTTP).typeVersion = 4.9; }, /typeVersion 4\.9 yok/],
  'Code düğümünde yanlış alan adı': [(w) => {
    const p = dugum(w, 'Değişiklik Tespiti').parameters; p.code = p.jsCode; delete p.jsCode;
  }, /code: bilinmeyen parametre/],
  'geçersiz onError': [(w) => { dugum(w, HTTP).onError = 'continue'; }, /onError: geçersiz/],
  'IF düğümüne 3. çıkış bağlanması': [(w) => {
    w.connections['Veri Geçerli mi?'].main.push([{ node: 'Hata Mesajı Hazırla', type: 'main', index: 0 }]);
  }, /3 çıkış bağlı, düğümün 2 çıkışı var/],
  'number yerine string': [(w) => { dugum(w, HTTP).parameters.options.pagination.pagination.maxRequests = '50'; }, /number olmalı/],
  'geçersiz resourceLocator modu': [(w) => { dugum(w, OKU).parameters.sheetName.mode = 'gid'; }, /mode: geçersiz "gid"/],
};

for (const [ad, [boz, beklenen]] of Object.entries(MUTASYONLAR)) {
  test(`doğrulayıcı yakalar: ${ad}`, secenek, () => {
    const w = temiz();
    boz(w);
    const bulunan = hatalar(w);
    assert.ok(bulunan.some((h) => beklenen.test(h)), `beklenen hata yok; bulunan: ${JSON.stringify(bulunan)}`);
  });
}
