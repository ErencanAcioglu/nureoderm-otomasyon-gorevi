// n8n Code düğümü kodunu Node.js'te çalıştırmak için küçük kum havuzu (sandbox).
// Testler kod/*.js dosyalarını değil, workflow.json İÇİNE GÖMÜLÜ kodu çalıştırır:
// yani n8n'e import edilecek olan kodun kendisi test edilir.

'use strict';

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const KOK = path.resolve(__dirname, '..');
const WORKFLOW = JSON.parse(fs.readFileSync(path.join(KOK, 'workflow.json'), 'utf8'));

function dugum(ad) {
  const bulunan = WORKFLOW.nodes.find((n) => n.name === ad);
  if (!bulunan) throw new Error(`workflow.json içinde düğüm yok: ${ad}`);
  return bulunan;
}

const itemler = (liste) => liste.map((json) => ({ json }));

/**
 * @param {string} dugumAdi  workflow.json'daki Code düğümünün adı
 * @param {object} secenek   girdi: $input item'larının json listesi; dugumler: { ad: [json, ...] } → $('ad')
 * @returns {object[]}       düğümün döndürdüğü item'ların json listesi
 */
function kodCalistir(dugumAdi, { girdi = [], dugumler = {} } = {}) {
  const jsKodu = dugum(dugumAdi).parameters.jsCode;
  const girdiItemleri = itemler(girdi);
  const $input = { all: () => girdiItemleri, first: () => girdiItemleri[0] };
  const $ = (ad) => {
    if (!(ad in dugumler)) throw new Error(`Kod, sağlanmamış bir düğüme başvurdu: $('${ad}')`);
    const liste = itemler(dugumler[ad]);
    return { all: () => liste, first: () => liste[0] };
  };
  const sonuc = vm.runInNewContext(`(function () {\n${jsKodu}\n})()`, { $input, $, console });
  if (!Array.isArray(sonuc)) throw new Error(`${dugumAdi} dizi döndürmedi`);
  // vm bağlamındaki nesneleri test bağlamına taşı (farklı prototipler deepEqual'ı bozar)
  return JSON.parse(JSON.stringify(sonuc)).map((item) => item.json);
}

/** HTTP düğümündeki sayfalama bitiş ifadesini ($response → boolean) fonksiyona çevirir. */
function sayfalamaBittiMi() {
  const ifade = dugum('Laptop Sayfalarını Çek (Sayfalama)').parameters.options.pagination.pagination.completeExpression;
  const govde = ifade.replace(/^=\{\{/, '').replace(/\}\}$/, '');
  // eslint-disable-next-line no-new-func
  return new Function('$response', `return (${govde});`);
}

const fixture = (ad) => fs.readFileSync(path.join(__dirname, 'fixtures', ad), 'utf8');

module.exports = { WORKFLOW, KOK, dugum, kodCalistir, sayfalamaBittiMi, fixture };
