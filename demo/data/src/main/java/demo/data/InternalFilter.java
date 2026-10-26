package demo.data;

import jakarta.servlet.*;
import jakarta.servlet.http.*;
import org.springframework.stereotype.Component;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.filter.OncePerRequestFilter;
import java.io.IOException;
@Component
public class InternalFilter extends OncePerRequestFilter {
    @Value("${lab.internal-key}") private String key;
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain) throws ServletException, IOException {
        if (!"/health".equals(req.getRequestURI()) && !key.equals(req.getHeader("X-Internal-Key"))) { res.sendError(403); return; }
        chain.doFilter(req,res);
    }
}
