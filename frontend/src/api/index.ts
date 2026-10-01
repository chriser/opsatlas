// The control panel's API client, one module per area (split in AUDIT F13). Pages import from here, as "./api";
// the modules import each other directly. Calls are same-origin: the Sales app serves the panel and the API, and
// the Vite dev server proxies /api and /services to it.

export {
  AUTH_INVALID_EVENT, AccessDenied, AuthError, ME_CHANGED_EVENT, PRODUCT_GUIDE, ReauthRequired, apiRequest, apiUpload,
  authHeaders, can, currentMe, fetchMe, getActiveSpace, getSocketTicket, isAuthenticated, lastInteractionAt, login,
  logout, noteInteraction, setActiveSpace, spaceHeader,
} from "./http";
export type { Me, MeSpace } from "./http";
export { approveSource, deleteSource, ingestSource, listSources, rejectSource, uploadSource } from "./sources";
export type { SourceRecord } from "./sources";
export { askQuestion, createAvatarSessionToken, getAvatarConfig, getTraces, searchKnowledge } from "./answers";
export type { AnswerResponse, AuditRecord, AvatarConfig, Citation, SearchResponse, SearchResult } from "./answers";
export {
  deleteProcessInterview, getProcessDiagram, getProcessDiagramServiceStatus, getProcessInterview, getProcessMap,
  getProcessRegistry, listProcessInterviews, renderInterviewMap, resolveProcessDiagram, saveProcessCapture,
  startProcessDiagramService,
} from "./process";
export type {
  InterviewedProcess, ProcessDiagramAnimationStep, ProcessDiagramChart, ProcessDiagramContext, ProcessDiagramEdge,
  ProcessDiagramNode, ProcessDiagramPoint, ProcessDiagramServiceStatus, ProcessInterviewSession,
  ProcessInterviewSummary, ProcessMapDraft, ProcessModel, ProcessNote, ProcessOpenItem, ProcessQuote, ProcessRecord,
  ProcessRule, ProcessStep,
} from "./process";
export { getEamModel, getEamSvg } from "./eam";
export type {
  EamCell, EamCoverage, EamDomainCoverage, EamEdge, EamEntityRollup, EamFinding, EamModel, EamNode, EamTaxonomyEntry,
} from "./eam";
export { approveOntologyProposal, declineOntologyProposal, getActionLog, runOntologyInvestigation } from "./ontology";
export type { ActionExecution, AgentRunTrace, AgentStep, PendingActionProposal, ProposedAction } from "./ontology";
export {
  captureGovernanceSnapshot, createImprovementAction, getAnalyticsCharts, getAnalyticsComputationTraces,
  getAnalyticsDictionaryMarkdown, getAnalyticsExportDataset, getAnalyticsExportIndex, getAnalyticsForecast,
  getAnalyticsMethods, getAnalyticsReportMarkdown, getAnalyticsReportPdf, getAnalyticsReproducibilityPack,
  getGovernanceHistory, getImprovementActions, getImprovementMetrics, getKnowledgeGaps, getOagBenchmark,
  getOagOperations, getOntologyStats, getProcessComplexity, getRecurringQuestions, getRetrievalHealth, getScorecard,
  getValidationEvidence, transitionImprovementAction,
} from "./analytics";
export type {
  AnalyticsComputationTrace, AnalyticsComputationTraceReport, AnalyticsExportDatasetSummary, AnalyticsExportFormat,
  AnalyticsExportIndex, AnalyticsForecastPoint, AnalyticsForecastReport, AnalyticsMethod, AnalyticsMethodReference,
  AnalyticsMethodsCatalogue, AnalyticsSeriesPoint, ChartData, EthicsNote, EvidenceHistoryEntry, EvidenceReference,
  GovernanceHistory, ImprovementAction, ImprovementActionCreatePayload, ImprovementActionList,
  ImprovementActionTransitionPayload, ImprovementLoopMetrics, ImprovementNote, ImprovementReviewCadence,
  ImprovementStatus, ImprovementTriggerType, KnowledgeGapAnalytics, KnowledgeGapCluster, KsbTraceabilityRow,
  OagBenchmarkDetailRow, OagBenchmarkLiftRow, OagBenchmarkMatrixRow, OagBenchmarkMetric, OagBenchmarkReport,
  OagBenchmarkScorecard, OagOperationsReport, OfficialKsbReference, OntologyStats, ProcessComplexityAnalytics,
  ProcessComplexityRow, RecurringQuestionAnalytics, RecurringQuestionGroup, RetrievalHealthAnalytics,
  RetrievalHealthPattern, Scorecard, ValidationEvidenceReport, ValidationProtocolRow,
} from "./analytics";
export {
  deleteExternalSource, getRegulatoryCandidates, listExternalSnapshots, listExternalSources,
  reviewRegulatoryCandidate, simulateRegulatoryImpact, snapshotGovUkSource,
} from "./external";
export type {
  PublicContentSnapshot, PublicContentSource, RegulatoryCandidate, RegulatoryCandidateReport,
  RegulatoryImpactSimulation,
} from "./external";
export {
  SPACES_CHANGED, changeSpace, createSpace, getHealthDetails, listSpaces, restartServices, startDiagramService,
  transferDocument,
} from "./system";
export type { HealthResponse, Space } from "./system";
export {
  TibiServiceError, askTibiText, closeTibiText, confirmTibiFact, draftTibiSpoken, getTibiContributions,
  getTibiGovernanceAnswers, getTibiGovernanceSummary, getTibiOntology, getTibiRecords, getTibiServiceToken,
  getTibiSource, getTibiSpoken, getTibiStatementReview, getTibiStatus, openTibiText, proposeTibiClaim,
  resolveTibiRecord, reviewTibiGovernanceAnswer, reviewTibiRecord, reviewTibiSpoken, runTibiStatementReview,
  tibiServiceDelete, tibiServiceGet, tibiServicePost,
} from "./tibi";
export type {
  TibiContribution, TibiGovernanceAnswer, TibiGovernanceSummary, TibiOntology, TibiOntologyObject, TibiOpenIssue,
  TibiRecord, TibiRecordStatement, TibiSpokenVariant, TibiStatementFinding, TibiStatementReview, TibiStatus,
  TibiTextTurn,
} from "./tibi";
