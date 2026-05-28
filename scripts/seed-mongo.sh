#!/usr/bin/env bash
# Seed the local MongoDB with a few demo grant_applications.
# Usage:  ./scripts/seed-mongo.sh   (run after `docker-compose up`)

set -euo pipefail

MONGO_URL="${MONGO_URL:-mongodb://app:app_dev_password@localhost:27017}"

cat <<'EOF' | docker run --rm -i --network host mongo:7 mongosh "$MONGO_URL/grants_portal_modern?authSource=admin"
db.grant_applications.insertMany([
  {
    agencyId: "HHS-ACF",
    title: "Community Health Worker Capacity-Building in Rural Clinics",
    description: "<p>Expands the community health worker workforce across 11 rural counties to improve preventive-care access.</p>",
    status: "INTAKE",
    opportunityNumber: "HHS-2026-ACF-OCS-EE-0142",
    assistanceListingNumber: "93.243",
    awardingAgency: "HHS-ACF",
    applicantOrg: "Appalachian Regional Health Coalition",
    applicantUei: "AB1CDE2FGHI3",
    applicantType: "NONPROFIT",
    principalInvestigator: "Dr. Maria Alvarez",
    fundingInstrument: "GRANT",
    requestedAmountFederal: 1250000,
    costShareMatch: 250000,
    createdAt: new Date(),
    updatedAt: new Date()
  },
  {
    agencyId: "NSF",
    title: "Undergraduate Research in Coastal Resilience Modeling",
    description: "Cooperative agreement establishing an undergraduate research-experience program in coastal-resilience modeling.",
    status: "SCREENING",
    opportunityNumber: "NSF-26-0203",
    assistanceListingNumber: "47.050",
    awardingAgency: "NSF",
    applicantOrg: "State University of Example",
    applicantUei: "ZX9YWV8UTSR7",
    applicantType: "IHE",
    principalInvestigator: "Dr. Samuel Park",
    fundingInstrument: "COOPERATIVE_AGREEMENT",
    requestedAmountFederal: 600000,
    costShareMatch: 0,
    createdAt: new Date(),
    updatedAt: new Date()
  }
]);
print("Seeded " + db.grant_applications.countDocuments() + " grant_applications.");
EOF
