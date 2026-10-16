/** Root application component. */

import { useEffect, useState } from "react";
import type { CasinosData } from "@/types";
import CasinoTable from "@/components/CasinoTable";

/** URL of the casinos.json file served alongside the frontend. */
const JSON_URL = "casinos.json";

export default function App() {
  const [data, setData] = useState<CasinosData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadData(): Promise<void> {
      try {
        const response = await fetch(JSON_URL, { cache: "no-store" });
        if (!response.ok) {
          throw new Error(`Failed to load casinos.json: ${response.status}`);
        }
        const json: CasinosData = await response.json();
        if (!cancelled) {
          setData(json);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Unknown error loading casino data"
          );
        }
      }
    }

    loadData();
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <div className="min-h-screen p-4 sm:p-6 md:p-8 lg:p-12 bg-gray-50 text-center">
        <h1 className="text-3xl font-bold text-gray-900 leading-tight mb-4">
          Casino Bonus Scraper
        </h1>
        <p className="text-red-600 mb-6">{error}</p>
        <p className="text-red-600 mb-6">
Unable to load casino data. Check that casinos.json is deployed to the root of your site, then refresh the page.
</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen p-4 bg-gray-50 text-center">
        <h1 className="text-2xl font-bold text-gray-900 mb-4">
          Casino Bonus Scraper
        </h1>
        <p className="text-gray-500 animate-pulse">Loading casino data...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-4 sm:p-6 md:p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">
          Casino Bonus Scraper
        </h1>
        <p className="mt-2 text-gray-600">
          Welcome bonus data for {data.count} casino{data.count !== 1 ? "s" : ""},
          scraped from a public source.
        </p>
      </header>

      <CasinoTable casinos={data.casinos} source={data.source} />

      <footer className="mt-12 pt-8 border-t border-gray-200 text-xs text-gray-400">
        Casino Bonus Scraper &mdash; built with React 19 + TypeScript + Vite
      </footer>
    </div>
  );
}