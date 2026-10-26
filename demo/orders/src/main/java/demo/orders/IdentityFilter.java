package demo.orders;

import jakarta.servlet.*;
import jakarta.servlet.http.*;
import org.springframework.stereotype.Component;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.annotation.Order;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.web.filter.OncePerRequestFilter;
import java.io.IOException;
import java.util.List;
@Component
@Order(0)
public class IdentityFilter extends OncePerRequestFilter {
    @Value("${lab.internal-key}") private String key;
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain) throws ServletException, IOException {
        if ("/health".equals(req.getRequestURI())) { chain.doFilter(req,res); return; }
        if (!key.equals(req.getHeader("X-Internal-Key"))) { res.sendError(403); return; }
        try {
            String role = req.getHeader("X-Role");
            AuthContext.Principal p = new AuthContext.Principal(Long.parseLong(req.getHeader("X-User-Id")), Long.parseLong(req.getHeader("X-Tenant-Id")), role);
            SecurityContextHolder.getContext().setAuthentication(new UsernamePasswordAuthenticationToken(p, null, List.of(new SimpleGrantedAuthority("ROLE_"+role))));
            chain.doFilter(req,res);
        } finally { SecurityContextHolder.clearContext(); }
    }
}
