/** Admin Portföy Panosu — tüm müşteri tesislerinin canlı durumu */
import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import PortfolioBoard from "../shared/PortfolioBoard";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PortfolioBoardPanel() {
  const [data, setData] = useState(null);
  useEffect(() => {
    axios.get(`${API}/owner-pulse/portfolio/overview`).then(r => setData(r.data)).catch(() => toast.error("Portföy yüklenemedi"));
  }, []);
  return (
    <div data-testid="admin-portfolio-panel">
      <PortfolioBoard data={data} fetchRecovery={(pid) => axios.get(`${API}/owner-pulse/portfolio/recovery/${pid}`).then(r => r.data)} />
    </div>
  );
}
