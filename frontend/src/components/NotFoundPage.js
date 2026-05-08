import React from "react";
import { House, MagnifyingGlass } from "@phosphor-icons/react";

export default function NotFoundPage() {
  return (
    <div
      className="min-h-screen bg-stone-50 flex items-center justify-center p-6"
      data-testid="not-found-page"
    >
      <div className="max-w-md w-full text-center">
        <div className="w-20 h-20 mx-auto mb-5 rounded-full bg-amber-100 inline-flex items-center justify-center">
          <MagnifyingGlass size={36} weight="bold" className="text-amber-600" />
        </div>
        <div className="text-6xl font-bold text-stone-900 mb-2">404</div>
        <div className="text-lg font-semibold text-stone-800 mb-2">Sayfa bulunamadı</div>
        <p className="text-sm text-stone-500 mb-6">
          Aradığınız sayfa taşınmış, silinmiş veya hiç var olmamış olabilir.
        </p>
        <a
          href="/"
          data-testid="not-found-home"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-md bg-stone-900 text-white text-sm font-semibold hover:bg-stone-800"
        >
          <House size={16} weight="fill" /> Ana Sayfaya Dön
        </a>
      </div>
    </div>
  );
}
