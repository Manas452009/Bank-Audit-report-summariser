package com.project.bars.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;

import java.util.Map;

@Service
public class PythonAnalysisService {

    private final RestClient restClient;

    public PythonAnalysisService(@Value("${analysis.python.base-url}") String pythonBaseUrl) {
        this.restClient = RestClient.builder()
                .baseUrl(pythonBaseUrl)
                .build();
    }

    public Map<String, Object> processPdf(String filename, byte[] content) {
        HttpHeaders fileHeaders = new HttpHeaders();
        fileHeaders.setContentType(MediaType.APPLICATION_PDF);
        fileHeaders.setContentDisposition(ContentDisposition.formData().name("file").filename(filename).build());

        HttpEntity<ByteArrayResource> fileEntity = new HttpEntity<>(new NamedByteArrayResource(content, filename), fileHeaders);

        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("file", fileEntity);

        return restClient.post()
                .uri("/process-pdf")
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(body)
                .retrieve()
                .body(Map.class);
    }

    public Map<String, Object> generateSummary(Map<String, Object> payload) {
        return restClient.post()
                .uri("/generate-summary")
                .contentType(MediaType.APPLICATION_JSON)
                .body(payload)
                .retrieve()
                .body(Map.class);
    }

    private static final class NamedByteArrayResource extends ByteArrayResource {

        private final String filename;

        private NamedByteArrayResource(byte[] byteArray, String filename) {
            super(byteArray);
            this.filename = filename;
        }

        @Override
        public String getFilename() {
            return filename;
        }
    }
}
