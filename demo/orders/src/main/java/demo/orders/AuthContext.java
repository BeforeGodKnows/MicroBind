package demo.orders;

import org.springframework.security.core.context.SecurityContextHolder;
public final class AuthContext {
    public static long userId() { return ((Principal)SecurityContextHolder.getContext().getAuthentication().getPrincipal()).userId; }
    public static long tenantId() { return ((Principal)SecurityContextHolder.getContext().getAuthentication().getPrincipal()).tenantId; }
    public static String role() { return ((Principal)SecurityContextHolder.getContext().getAuthentication().getPrincipal()).role; }
    public static class Principal {
        public final long userId, tenantId;
        public final String role;
        public Principal(long userId, long tenantId, String role) { this.userId=userId; this.tenantId=tenantId; this.role=role; }
    }
}
