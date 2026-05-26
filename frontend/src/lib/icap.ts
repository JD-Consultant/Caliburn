import type { IcapCandidate } from "@/types";

export function icapConfidenceLabel(candidate: IcapCandidate): string {
  if (candidate.confidence_label) return candidate.confidence_label;
  return {
    high: "高信心",
    medium: "中信心",
    low: "低信心",
  }[candidate.confidence];
}

export function icapRecommendationLabel(candidate: IcapCandidate): string {
  return {
    建議參考: "主要參考",
    部分參考: "可參考",
    主要參考: "主要參考",
    可參考: "可參考",
    低信心: "低信心",
  }[candidate.recommendation];
}

export function icapCandidateTone(candidate: IcapCandidate): string {
  if (candidate.confidence === "high") {
    return "bg-emerald-100 text-emerald-800 border-emerald-200";
  }
  if (candidate.confidence === "medium") {
    return "bg-blue-100 text-blue-800 border-blue-200";
  }
  return "bg-gray-100 text-gray-600 border-gray-200";
}
