package com.project.bars.service;

import com.project.bars.dto.ReportSummaryRequest;
import com.project.bars.dto.ReportSummaryResponse;
import org.springframework.stereotype.Service;

import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.stream.Collectors;

@Service
public class ReportSummaryService {

    private static final List<String> FINDING_KEYWORDS = List.of(
            "risk", "fraud", "compliance", "exception", "breach", "irregularity",
            "non-compliant", "delay", "mismatch", "overdue", "violation", "weakness"
    );

    public ReportSummaryResponse summarize(ReportSummaryRequest request) {
        List<String> findings = Arrays.stream(request.getReportText().split("\\r?\\n"))
                .map(String::trim)
                .filter(line -> !line.isBlank())
                .filter(this::looksLikeFinding)
                .limit(5)
                .collect(Collectors.toList());

        if (findings.isEmpty()) {
            findings = List.of("No major audit exceptions were detected in the submitted report text.");
        }

        String riskLevel = determineRiskLevel(request.getReportText(), findings.size());
        String bankName = valueOrDefault(request.getBankName(), "the bank");
        String branchName = valueOrDefault(request.getBranchName(), "the audited branch");
        String auditDate = valueOrDefault(request.getAuditDate(), "the submitted audit period");

        String summary = String.format(
                "Audit summary for %s at %s on %s: %d key finding(s) were highlighted. Overall risk appears %s based on the submitted report content.",
                bankName,
                branchName,
                auditDate,
                findings.size(),
                riskLevel.toLowerCase(Locale.ROOT)
        );

        return new ReportSummaryResponse(summary, riskLevel, findings, findings.size());
    }

    private boolean looksLikeFinding(String line) {
        String normalized = line.toLowerCase(Locale.ROOT);
        return FINDING_KEYWORDS.stream().anyMatch(normalized::contains);
    }

    private String determineRiskLevel(String reportText, int findingCount) {
        long hits = FINDING_KEYWORDS.stream()
                .filter(keyword -> reportText.toLowerCase(Locale.ROOT).contains(keyword))
                .count();

        long score = hits + findingCount;
        if (score >= 8) {
            return "HIGH";
        }
        if (score >= 4) {
            return "MEDIUM";
        }
        return "LOW";
    }

    private String valueOrDefault(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }
}
