import axios from "axios";
import OwnerRatesBoard from "../shared/OwnerRatesBoard";

const BASE = `${process.env.REACT_APP_BACKEND_URL}/api/owner-rates`;

export default function OwnerRatesAdminPanel({ propertyId = "default" }) {
  const pid = propertyId === "all" ? "default" : propertyId;
  const DS = `${process.env.REACT_APP_BACKEND_URL}/api/discount-stack/${pid}`;
  const api = {
    getBoard: async (days) => (await axios.get(`${BASE}/${pid}/board?days=${days}`)).data,
    setRate: async (p) => (await axios.post(`${BASE}/${pid}/manual-rate`, p)).data,
    addLayer: async (p) => (await axios.post(`${DS}/layers`, p)).data,
    toggleLayer: async (id, active) => (await axios.put(`${DS}/layers/${id}`, { active })).data,
    deleteLayer: async (id) => (await axios.delete(`${DS}/layers/${id}`)).data,
  };
  return (
    <div className="space-y-5" data-testid="owner-rates-admin-panel">
      <div className="relative bg-[#0A0F1C] rounded-2xl p-6 text-white overflow-hidden">
        <div className="absolute top-[-60px] right-[-40px] w-[240px] h-[240px] rounded-full bg-[#06B6D4]/20 blur-3xl" aria-hidden="true" />
        <div className="relative">
          <div className="text-[11px] uppercase tracking-[0.18em] text-cyan-300 mb-1">Revenue Management · İki Yönlü Pano</div>
          <h2 className="text-2xl font-bold">Sahip Fiyat Panosu (Admin Görünümü)</h2>
          <p className="text-sm text-stone-400 mt-1 max-w-2xl">
            Otel sahibinin portalında gördüğü panonun aynısı. Fiyata tıklayıp değiştirin —
            brüt (PMS) veya müşteri fiyatı girin, sistem diğerini hesaplar. Sahip tarafındaki
            değişiklikler burada "SAHİP" etiketiyle görünür.
          </p>
        </div>
      </div>
      <OwnerRatesBoard api={api} title="Fiyatlar" />
    </div>
  );
}
