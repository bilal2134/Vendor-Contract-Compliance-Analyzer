export type FindingStatus =
  | "compliant"
  | "partial"
  | "non_compliant"
  | "missing"
  | "conflict";

export type Severity = "critical" | "high" | "medium" | "low";

export interface Citation {
  source_id: string;
  source_name: string;
  page: number | null;
  section: string | null;
  excerpt: string;
  locator: string | null;
}

export interface ConfidenceBreakdown {
  extraction: number;
  retrieval: number;
  grounding: number;
  rule_completion: number;
}

export interface Finding {
  finding_id: string;
  title: string;
  category: string;
  severity: Severity;
  status: FindingStatus;
  summary: string;
  policy_citation: Citation;
  vendor_citations: Citation[];
  confidence: number;
  confidence_breakdown: ConfidenceBreakdown;
  search_summary: string;
}

export interface ConflictRecord {
  conflict_id: string;
  title: string;
  summary: string;
  left_citation: Citation;
  right_citation: Citation;
  severity: Severity;
}

export interface ReportSummary {
  compliant: number;
  partial: number;
  non_compliant: number;
  missing: number;
  conflicts: number;
}

export interface PackageReport {
  report_id: string;
  package_id: string;
  vendor_name: string;
  playbook_version_id: string;
  summary: ReportSummary;
  findings: Finding[];
  conflicts: ConflictRecord[];
}

export interface DashboardCard {
  package_id: string;
  vendor_name: string;
  status: string;
  critical_findings: number;
  report_id: string | null;
}

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api";

export interface PlaybookSummary {
  version_id: string;
  name: string;
  effective_date: string;
  description: string | null;
  requirement_count: number;
  status: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function getDashboard(): Promise<{ cards: DashboardCard[] }> {
  return request("/reports/dashboard");
}

export function getReport(reportId: string): Promise<PackageReport> {
  return request(`/reports/${reportId}`);
}

export function getPlaybooks(): Promise<{ items: PlaybookSummary[] }> {
  return request("/ingestion/playbooks");
}
