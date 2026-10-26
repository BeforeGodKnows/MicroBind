package demo.orders;

import feign.RequestInterceptor;
import org.springframework.context.annotation.*;
import org.springframework.beans.factory.annotation.Value;
@Configuration
public class FeignConfig {
    @Bean public RequestInterceptor internalKey(@Value("${lab.internal-key}") String key) {
        return template -> template.header("X-Internal-Key", key);
    }
}
