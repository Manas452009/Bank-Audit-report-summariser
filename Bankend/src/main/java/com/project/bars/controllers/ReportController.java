package com.project.bars.controllers;

import com.project.bars.dto.ReportSummaryRequest;
import com.project.bars.dto.ReportSummaryResponse;
import com.project.bars.service.ReportProcessingService;
import com.project.bars.service.ReportSummaryService;
import jakarta.validation.Valid;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

@RestController
@RequestMapping("/api/reports")
public class ReportController {

    private final ReportSummaryService reportSummaryService;
    private final ReportProcessingService reportProcessingService;

    public ReportController(ReportSummaryService reportSummaryService,
                            ReportProcessingService reportProcessingService) {
        this.reportSummaryService = reportSummaryService;
        this.reportProcessingService = reportProcessingService;
    }

    @GetMapping("/me")
    public Map<String, String> currentUser(Authentication authentication) {
        return Map.of(
                "message", "Authenticated request successful",
                "username", authentication.getName()
        );
    }

    @PostMapping("/summarize")
    public ReportSummaryResponse summarizeReport(@Valid @RequestBody ReportSummaryRequest request) {
        return reportSummaryService.summarize(request);
    }

    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Map<String, Object> uploadReport(@RequestParam("file") MultipartFile file) {
        return reportProcessingService.uploadAndAnalyze(file);
    }

    @PostMapping("/generate-summary")
    public Map<String, Object> generateSummary(@RequestBody Map<String, Object> request) {
        return reportProcessingService.generateSummary(request);
    }

    @PostMapping("/download-report")
    public ResponseEntity<byte[]> downloadReport(@RequestBody Map<String, Object> request) {
        Map<String, Object> payload = (Map<String, Object>) request.getOrDefault("data", request);
        return reportProcessingService.downloadJson("report", payload);
    }

    @PostMapping("/download-summary")
    public ResponseEntity<byte[]> downloadSummary(@RequestBody Map<String, Object> request) {
        Map<String, Object> payload = (Map<String, Object>) request.getOrDefault("summary", request);
        return reportProcessingService.downloadJson("summary", payload);
    }
}
