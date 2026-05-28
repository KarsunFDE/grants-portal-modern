package com.karsunfde.grantsportal.grantapplication.dto;

/**
 * Create-grantApplication request DTO.
 *
 * ⚠ DELIBERATE — Item 9:
 *   No {@code @SafeHtml}, no {@code @NotBlank}, no length cap on
 *   {@code description}. The field accepts {@code <script>} tags verbatim.
 *   Cohort fixes in W4 Wed AI Security Engineering Day.
 *
 * ⚠ DELIBERATE — Item 10 reinforcement:
 *   {@code agencyId} is on the DTO but the controller doesn't cross-check it
 *   against the JWT's agency claim.
 *
 * ⚠ DELIBERATE — Pair-unique debt obs-pii-in-info-logs (D-059):
 *   {@code principalInvestigatorName} + {@code applicantSsn} are PII fields
 *   accepted on the request. {@link
 *   com.karsunfde.grantsportal.grantapplication.service.GrantApplicationService#create}
 *   logs both at INFO level — FedRAMP MP-6 / AU-2 violation. Cohort fixes
 *   W5.
 */
public class GrantApplicationCreateRequest {

    private String agencyId;
    private String title;
    private String description; // ⚠ raw HTML accepted
    private String status;

    // --- Grants intake fields (SF-424 / 2 CFR 200) ---
    private String opportunityNumber;
    private String assistanceListingNumber;
    private String awardingAgency;
    private String applicantOrg;
    private String applicantUei;
    private String applicantType;
    private String fundingInstrument;
    private Double requestedAmountFederal;
    private Double costShareMatch;

    // ⚠ Pair-unique debt obs-pii-in-info-logs — PI name + SSN feed the
    //   INFO-level log line in GrantApplicationService.create.
    private String principalInvestigatorName;
    private String applicantSsn;

    public GrantApplicationCreateRequest() {}

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
    public String getFundingInstrument() { return fundingInstrument; }
    public void setFundingInstrument(String fundingInstrument) { this.fundingInstrument = fundingInstrument; }
    public Double getRequestedAmountFederal() { return requestedAmountFederal; }
    public void setRequestedAmountFederal(Double requestedAmountFederal) { this.requestedAmountFederal = requestedAmountFederal; }
    public Double getCostShareMatch() { return costShareMatch; }
    public void setCostShareMatch(Double costShareMatch) { this.costShareMatch = costShareMatch; }

    public String getPrincipalInvestigatorName() { return principalInvestigatorName; }
    public void setPrincipalInvestigatorName(String principalInvestigatorName) {
        this.principalInvestigatorName = principalInvestigatorName;
    }
    public String getApplicantSsn() { return applicantSsn; }
    public void setApplicantSsn(String applicantSsn) { this.applicantSsn = applicantSsn; }
}
