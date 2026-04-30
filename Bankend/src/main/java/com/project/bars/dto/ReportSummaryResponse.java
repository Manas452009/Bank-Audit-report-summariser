package com.project.bars.dto;

import java.util.List;

public class ReportSummaryResponse {

    private String executiveSummary;
    private String riskLevel;
    private List<String> keyFindings;
    private int findingCount;

    public ReportSummaryResponse() {
    }

    public ReportSummaryResponse(String executiveSummary, String riskLevel, List<String> keyFindings, int findingCount) {
        this.executiveSummary = executiveSummary;
        this.riskLevel = riskLevel;
        this.keyFindings = keyFindings;
        this.findingCount = findingCount;
    }

    public String getExecutiveSummary() {
        return executiveSummary;
    }

    public void setExecutiveSummary(String executiveSummary) {
        this.executiveSummary = executiveSummary;
    }

    public String getRiskLevel() {
        return riskLevel;
    }

    public void setRiskLevel(String riskLevel) {
        this.riskLevel = riskLevel;
    }

    public List<String> getKeyFindings() {
        return keyFindings;
    }

    public void setKeyFindings(List<String> keyFindings) {
        this.keyFindings = keyFindings;
    }

    public int getFindingCount() {
        return findingCount;
    }

    public void setFindingCount(int findingCount) {
        this.findingCount = findingCount;
    }
}
