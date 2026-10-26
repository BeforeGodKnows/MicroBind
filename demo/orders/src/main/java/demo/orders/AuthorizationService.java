package demo.orders;

import demo.common.Order;
import org.springframework.stereotype.Service;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.access.AccessDeniedException;
@Service
public class AuthorizationService {
    @Autowired private DataClient data;
    public void requireOwner(long objectId, long actorId) {
        Order order = data.get(objectId);
        if (order.getOwnerId() != actorId) { throw new AccessDeniedException("owner"); }
    }
    public boolean owns(long objectId, long actorId) {
        Order order = data.get(objectId);
        return order.getOwnerId() == actorId;
    }
    public void requireAdmin() {
        String role = AuthContext.role();
        if (!role.equals("ADMIN")) { throw new AccessDeniedException("role"); }
    }
}
