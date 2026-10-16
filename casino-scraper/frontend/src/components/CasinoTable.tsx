/** CasinoTable component: renders a responsive table of casino bonuses. */

import type { CasinoBonus } from "@/types";

interface CasinoTableProps {
  casinos: CasinoBonus[];
  source: string;
}

/** Format a wagering requirement for display. */
function formatWagering(value: number | null): string {
  if (value === null || value === undefined) return "N/A";
  return `${value}x`;
}

/** Format a scraped_at timestamp for display. */
function formatScrapedAt(value: string): string {
  try {
    return new Date(value).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return value;
  }
}

export default function CasinoTable({ casinos, source }: CasinoTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <caption className="sr-only visually-hidden">
          Casino bonus comparison table
        </caption>
        <caption className="caption-bottom text-xs text-gray-500">
          Table showing casino welcome bonuses with wagering requirements and minimum deposits
        </caption>
        <thead className="bg-gray-50">
          <tr>
            <th
              scope="col"
              className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Casino
            </th>
            <th
              scope="col"
              className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Welcome Bonus
            </th>
            <th
              scope="col"
              className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Wagering
            </th>
            <th
              scope="col"
              className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Min Deposit
            </th>
            <th
              scope="col"
              className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Source
            </th>
            <th
              scope="col"
              className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Scraped At
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {casinos.map((casino: CasinoBonus) => (
            <tr
              key={casino.name}
              className="hover:bg-gray-50 focus-visible:bg-gray-100"
            >
              <td className="px-6 py-4 whitespace-nowrap">
                <div className="text-sm font-medium text-gray-900">
                  {casino.name}
                </div>
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <div className="text-sm text-gray-900">
                  {casino.welcome_bonus ?? "N/A"}
                </div>
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <div className="text-sm text-gray-900">
                  {formatWagering(casino.wagering_requirement)}
                </div>
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <div className="text-sm text-gray-900">
                  {casino.minimum_deposit ?? "N/A"}
                </div>
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <a
                  href={casino.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-blue-600 hover:underline"
                >
                  View source
                </a>
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <div className="text-sm text-gray-500">
                  {formatScrapedAt(casino.scraped_at)}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-4 text-xs text-gray-500">
        <span className="sr-only">Data source: </span>
        Data source:{" "}
        <a
          href={source}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:underline"
        >
          {source}
        </a>
      </p>
    </div>
  );
}