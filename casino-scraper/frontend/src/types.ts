/** Type definitions for the casino bonus data. */

export interface CasinoBonus {
  name: string;
  welcome_bonus: string | null;
  wagering_requirement: number | null;
  minimum_deposit: string | null;
  source_url: string;
  scraped_at: string;
}

export interface CasinosData {
  casinos: CasinoBonus[];
  source: string;
  count: number;
}