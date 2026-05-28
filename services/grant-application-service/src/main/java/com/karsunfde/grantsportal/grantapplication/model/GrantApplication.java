package com.karsunfde.grantsportal.grantapplication.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

/**
 * GrantApplication document — Federal financial-assistance application
 * (SF-424 "Application for Federal Assistance" + 2 CFR 200 Uniform Guidance).
 * Reshaped W1 from the inherited acquisition shape to genuine grants fields:
 * NOFO/opportunity number, Assistance Listing (ALN/CFDA), applicant UEI,
 * applicant type, project title/narrative, principal investigator, funding
 * instrument, federal request + cost-share match, and period of performance.
 *
 * ⚠ DELIBERATE — Item 10:
 *   {@code agencyId} is in the schema (so the data is multi-tenant-shaped)
 *   but the repository does not filter on it. Cohort fixes in W2 Wed
 *   multi-tenant retrieval-boundary work.
 *
 * ⚠ DELIBERATE — Item 9:
 *   {@code description} is not sanitized; arbitrary HTML accepted on write
 *   and returned verbatim on read. Cohort fixes in W4 Wed AI Security
 *   Engineering Day (prompt-injection-via-stored-content — description
 *   feeds the ai-orchestrator prompt). The {@code sections} map (project
 *   narrative / budget narrative / merit-criteria text) carries the same
 *   un-sanitized-text debt.
 *
 * Workflow statuses (2 CFR 200 Subparts C → D):
 *   INTAKE -> SCREENING -> PEER_REVIEW -> AWARD_DECISION -> POST_AWARD_REPORTING
 *   -> (CLOSEOUT). WITHDRAWN is reachable from any pre-AWARD_DECISION state.
 */
@Document(collection = "grantApplications")
public class GrantApplication {

    @Id
    private String id;

    /** ⚠ Item 10 — present but un-enforced (awarding-agency tenant key). */
    private String agencyId;

    /** SF-424 Descriptive Title of Applicant's Project (≤200 chars). */
    private String title;

    /** ⚠ Item 9 — accepts arbitrary HTML (public project abstract). */
    private String description;

    /** Workflow status (INTAKE / SCREENING / PEER_REVIEW / …). */
    private String status;

    /** NOFO / funding-opportunity number (SF-424). */
    private String opportunityNumber;
    /** Assistance Listing Number (CFDA / ALN), e.g., 93.243. */
    private String assistanceListingNumber;
    /** Awarding agency name, e.g., HHS-NIH, NSF, DOE. */
    private String awardingAgency;
    /** Applicant organization legal name (SF-424). */
    private String applicantOrg;
    /** Applicant SAM Unique Entity ID (12-char; replaced DUNS Apr 2022). */
    private String applicantUei;
    /** Applicant type code (e.g., A=State, M=Nonprofit, H=IHE). */
    private String applicantType;
    /** Principal Investigator / Project Director. */
    private String principalInvestigator;
    /** Funding instrument: GRANT or COOPERATIVE_AGREEMENT (2 CFR 200). */
    private String fundingInstrument;
    /** Federal funds requested (SF-424A). */
    private Double requestedAmountFederal;
    /** Non-federal cost-share / match (SF-424A). */
    private Double costShareMatch;
    /** Areas affected by the project (SF-424 item 14). */
    private String areasAffected;

    /**
     * Grants application sections — project narrative, budget narrative, and
     * merit-review criteria — stored as a JSON-ish map so the cohort can
     * extend without schema changes. ⚠ Item 9 — values unsanitized; feeds
     * /draft-grant-application prompts.
     */
    private Map<String, String> sections = new HashMap<>();

    private Instant periodOfPerformanceStart;
    private Instant periodOfPerformanceEnd;
    private Instant submittedAt;
    private Instant createdAt;
    private Instant updatedAt;

    public GrantApplication() {}

    // --- getters / setters ---

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getAgencyId() { return agencyId; }
    public void setAgencyId(String agencyId) { this.agencyId = agencyId; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getOpportunityNumber() { return opportunityNumber; }
    public void setOpportunityNumber(String opportunityNumber) { this.opportunityNumber = opportunityNumber; }

    public String getAssistanceListingNumber() { return assistanceListingNumber; }
    public void setAssistanceListingNumber(String assistanceListingNumber) { this.assistanceListingNumber = assistanceListingNumber; }

    public String getAwardingAgency() { return awardingAgency; }
    public void setAwardingAgency(String awardingAgency) { this.awardingAgency = awardingAgency; }

    public String getApplicantOrg() { return applicantOrg; }
    public void setApplicantOrg(String applicantOrg) { this.applicantOrg = applicantOrg; }

    public String getApplicantUei() { return applicantUei; }
    public void setApplicantUei(String applicantUei) { this.applicantUei = applicantUei; }

    public String getApplicantType() { return applicantType; }
    public void setApplicantType(String applicantType) { this.applicantType = applicantType; }

    public String getPrincipalInvestigator() { return principalInvestigator; }
    public void setPrincipalInvestigator(String principalInvestigator) { this.principalInvestigator = principalInvestigator; }

    public String getFundingInstrument() { return fundingInstrument; }
    public void setFundingInstrument(String fundingInstrument) { this.fundingInstrument = fundingInstrument; }

    public Double getRequestedAmountFederal() { return requestedAmountFederal; }
    public void setRequestedAmountFederal(Double requestedAmountFederal) { this.requestedAmountFederal = requestedAmountFederal; }

    public Double getCostShareMatch() { return costShareMatch; }
    public void setCostShareMatch(Double costShareMatch) { this.costShareMatch = costShareMatch; }

    public String getAreasAffected() { return areasAffected; }
    public void setAreasAffected(String areasAffected) { this.areasAffected = areasAffected; }

    public Map<String, String> getSections() { return sections; }
    public void setSections(Map<String, String> sections) { this.sections = sections; }

    public Instant getPeriodOfPerformanceStart() { return periodOfPerformanceStart; }
    public void setPeriodOfPerformanceStart(Instant periodOfPerformanceStart) { this.periodOfPerformanceStart = periodOfPerformanceStart; }

    public Instant getPeriodOfPerformanceEnd() { return periodOfPerformanceEnd; }
    public void setPeriodOfPerformanceEnd(Instant periodOfPerformanceEnd) { this.periodOfPerformanceEnd = periodOfPerformanceEnd; }

    public Instant getSubmittedAt() { return submittedAt; }
    public void setSubmittedAt(Instant submittedAt) { this.submittedAt = submittedAt; }

    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }

    public Instant getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(Instant updatedAt) { this.updatedAt = updatedAt; }
}
