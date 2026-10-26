package demo.gateway;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.client.HttpStatusCodeException;
import java.io.IOException;

@RestController
public class GatewayController {
    @Value("${lab.orders-url}") private String ordersUrl;
    @Value("${lab.internal-key}") private String key;
    private final RestTemplate http = new RestTemplate();
    @GetMapping("/health") public String health() { return "ok"; }
    @RequestMapping("/api/**")
    public ResponseEntity<byte[]> proxy(HttpServletRequest request) throws IOException {
        String token = request.getHeader("Authorization");
        String user, tenant, role;
        if ("Bearer alice-demo".equals(token)) { user="1"; tenant="10"; role="USER"; }
        else if ("Bearer bob-demo".equals(token)) { user="2"; tenant="20"; role="USER"; }
        else if ("Bearer admin-demo".equals(token)) { user="9"; tenant="10"; role="ADMIN"; }
        else { return ResponseEntity.status(401).body("unauthenticated".getBytes()); }
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        // The caller's identity headers are discarded and reconstructed here.
        headers.set("X-Internal-Key", key);
        headers.set("X-User-Id", user);
        headers.set("X-Tenant-Id", tenant);
        headers.set("X-Role", role);
        String query = request.getQueryString();
        String url = ordersUrl + request.getRequestURI().substring(4) + (query == null ? "" : "?" + query);
        try {
            return http.exchange(url, HttpMethod.valueOf(request.getMethod()), new HttpEntity<byte[]>(request.getInputStream().readAllBytes(), headers), byte[].class);
        } catch (HttpStatusCodeException e) {
            return ResponseEntity.status(e.getStatusCode()).contentType(MediaType.APPLICATION_JSON).body(e.getResponseBodyAsByteArray());
        }
    }
}
