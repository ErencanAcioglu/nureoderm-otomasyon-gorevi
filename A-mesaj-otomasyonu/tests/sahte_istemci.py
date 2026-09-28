"""Testler için ağsız sepet istemcisi. Veriler DummyJSON'un gerçek yanıtlarından alınmıştır."""

from otomasyon.api import SepetSorgusu, SorguDurumu, sepet_yorumla

GERCEK_SEPETLER = {
    3: {"id": 3, "userId": 3, "total": 1794.85,
        "products": [{"title": "Fish Steak", "quantity": 1}, {"title": "iPhone 13 Pro", "quantity": 1}]},
    4: {"id": 4, "userId": 4, "total": 689.93,
        "products": [{"title": "Sports Sneakers Off White Red", "quantity": 1},
                     {"title": "Dior J'adore", "quantity": 1}]},
    5: {"id": 5, "userId": 5, "total": 1467.88,
        "products": [{"title": "Samsung Galaxy Tab White", "quantity": 4},
                     {"title": "Soft Drinks", "quantity": 4}]},
    12: {"id": 12, "userId": 12, "total": 37767.32,
         "products": [{"title": "Sportbike Motorcycle", "quantity": 2},
                      {"title": "Rolex Submariner Watch", "quantity": 1}]},
}


class SahteIstemci:
    def __init__(self, sepetler=None, hatali=()):
        self.sepetler = GERCEK_SEPETLER if sepetler is None else sepetler
        self.hatali = set(hatali)
        self.cagrilar = []

    def sepet_getir(self, sepet_id):
        self.cagrilar.append(sepet_id)
        if sepet_id in self.hatali:
            return SepetSorgusu(sepet_id, SorguDurumu.HATA, hata="HTTP 503")
        veri = self.sepetler.get(sepet_id, {"message": f"Cart with id '{sepet_id}' not found"})
        return sepet_yorumla(sepet_id, veri)
