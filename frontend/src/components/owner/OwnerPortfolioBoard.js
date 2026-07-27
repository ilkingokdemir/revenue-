/** Owner Portföy sekmesi — sahip token'ı ile portföy panosu */
import { useEffect, useState } from "react";
import PortfolioBoard from "../shared/PortfolioBoard";

export default function OwnerPortfolioBoard({ ax }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    ax().get("/owner-pulse/portal/portfolio-overview").then(r => setData(r.data)).catch(e => setErr(e?.response?.data?.detail || "Yüklenemedi"));
  }, [ax]);
  if (err) return <div className="text-center py-12 text-rose-500 text-sm" data-testid="op-portfolio-error">{err}</div>;
  return <PortfolioBoard data={data} />;
}
