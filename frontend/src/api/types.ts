export interface ExperimentReport {
  available: boolean;
  run_id?: string;
  dataset?: string;
  unit?: string;
  unit_zh?: string;
  model_version?: string;
  splits?: { test?: { rows: number } };
  test_metrics?: { pred_lgbm?: { mae: number }; pred_same_weekday_mean4?: { mae: number } };
  limitations?: string[];
  series_scope?: string;
  series?: { date: string; store: string; actual: number; baseline: number; prediction: number }[];
}
export interface OperatingReport { summary?: Record<string, number | string | null> }
  export interface PredictionReview { prediction_id:number; target_date:string; dish_name:string; meal_period:string; predicted_mid:number; adjusted_qty:number|null; sold_qty?:number; prepared_qty?:number; prediction_error?:number; execution_error?:number|null; reason?:string; source_nature:string; history_cutoff:string }
export interface OperatingDashboard {
  summary?: { prepared?: number; sold?: number; leftover?: number; rescued?: number; businessDay?: string; business_day?: string; business_date?: string };
  trend?: { businessDay?: string; business_day?: string; prepared: number; sold: number }[];
  risks?: { name: string; risk_level: string; leftover_qty: number }[];
}
export interface Stall { id:number; name:string; location:string; status:string; dishCount:number; rating:number; todayRevenue:number; dish_count?:number; today_revenue?:number }
export interface Dish { id:number; name:string; stallName:string; price:number; unitCost:number; quantityUnit?:string; avgSales:number; leftoverRate:number; stall_name?:string; unit_cost?:number; quantity_unit?:string; avg_sales?:number; leftover_rate?:number }
export interface Alert { id:number; alert_type:string; business_date:string; dish_name:string; stall_name:string; dish_id:number; alert_message:string; risk_level:string; status:string }
export interface Session { name:string; role:string; demo:boolean }
export interface Summary { prepared?:number; sold?:number; leftover?:number; rescued?:number; revenue?:number; accuracy?:number; costSaved?:number; carbonSaved?:number; waterSaved?:number }
export interface Metadata { period_end?:string; records?:number; dishes?:number; statement?:string }
export interface TrendPoint { businessDay:string; prepared:number; sold:number; leftover:number }
export interface Order { id:number; order_no:string; dish_name:string; title:string; quantity:number; amount:number; pickup_code:string; pickup_location:string; status:string }
export interface Offer { id:number; dish_name:string; discount_rate:number; remaining_qty:number; offer_price:number; status:string; dishName?:string; discountRate?:number; remainingQty?:number; offerPrice?:number }
export interface Advice { summary:string; source:string; aiGenerated:boolean }
export interface OfferRecommendation { dishId:number; dishName:string; recommendedQty:number; recommendedPrice:number; discountRate:number; startTime:string; endTime:string; advice?:Advice }
export interface Prediction { predictionId:number; dishId:number; dishName:string; predictedLow:number; predictedMid:number; predictedHigh:number; firstBatch:number; replenishQty:number; stopHour:number; stopMinute:number; soldOutRisk:string; leftoverRisk:string; advice?:Advice; factors?:{name:string;detail:string}[]; intervalMethod?:string; intervalCalibrated?:boolean; confidenceKind?:string }
export interface DecisionPreview {
  engine:string; modelVersion:string; status:string; unavailableReason?:string|null;
  targetDate:string; dayOfWeek:number; categoryId:number;
  q05:number; q95:number; offset:number; intervalLow:number; intervalHigh:number; center:number; sigma:number;
  criticalRatio:number; underage:number; overage:number;
  quantity:number; firstBatch:number; replenish:number; price:number; unitCost:number;
  lossRate:number; effectiveUnitCost:number; regretUpper:number;
  coverage:number; calibrationMethod:string; notes:string[];
}
  export interface PredictionResponse { engineKey:string; modelVersion:string; prediction:Prediction; generatedAt:string; targetDate?:string; historyCutoff?:string; mealPeriod?:string; sourceNature?:string; historyLatestDate?:string; historySampleCount?:number; predictionCutoffAt?:string; revisionIds?:number[]; publicationWatermark?:number }
export interface PreparationPlanInputs { stockServings:number; capacityServings:number; minimumBatch:number; leadMinutes:number; preparationStart:string; serviceStart:string; serviceEnd:string }
export interface PreparationPlanResult { referenceDemand:number; firstBatch:number; replenishQty:number; plannedTotal:number; uncoveredDemand:number; latestReplenishStart:string|null; canReplenish:boolean; automaticExecution:boolean; warnings:string[] }
export interface PreparationPlan { id:number; predictionId:number; inputs:PreparationPlanInputs; plan:PreparationPlanResult; createdBy:string; createdAt:string }
export interface FeedbackRow { id:number; operation_id:number; business_date:string; meal_period:string; dish_id:number; dish_name:string; planned_qty:number; prepared_qty:number; sold_qty:number; discount_sold_qty:number; leftover_qty:number; revenue:number; weather:string; event_tag:string; recommendation_adopted:boolean; operator_name:string; submission_note:string; submission_type:string }
export interface LearningResult { operationId:number; summary:string }
export interface LearningStatus { records?:number }
export interface ImportPreview { ready:boolean; sampleCount:number; totalRows:number; format:string; sheetName:string; sampleRows:string[][]; missingFields:string[]; headers:string[] }
export interface ImportResult { batchId:number; imported:number; rejected:number; duplicates:number; errors:string[]; sourceEvidenceId:number; sourceSha256:string; sourceVerificationStatus:string }
export interface SourceEvidence { source_evidence_id:number; source_sha256:string; file_name:string; source_name:string; provider:string; declared_region:string; authorization_reference:string; verification_status:string; created_by:string; created_at:string }

export interface AssistantAdvice {
  intent: string; answer: string;
  citations: { type: string; ref: string }[];
  suggestedAction: { quantity: number; reason: string } | null;
  refusal: { code: string; reason: string } | null;
  modelVersion: string | null; calibrationSha256: string | null;
}
