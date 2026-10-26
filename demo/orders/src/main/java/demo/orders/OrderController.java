package demo.orders;

import demo.common.Order;
import demo.common.Product;
import demo.common.CancelRequest;
import org.springframework.web.bind.annotation.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.access.prepost.PreAuthorize;

@RestController
public class OrderController {
    @Autowired private DataClient data;
    @Autowired private AuthorizationService auth;
    @GetMapping("/missing/{id}")
    public Order missing(@PathVariable("id") long id) {
        return data.get(id);
    }

    @GetMapping("/safe/{id}")
    public Order safe(@PathVariable("id") long id) {
        auth.requireOwner(id, AuthContext.userId());
        return data.get(id);
    }

    @GetMapping("/post-read/{id}")
    public Order postRead(@PathVariable("id") long id) {
        Order result = data.get(id);
        if (result.getOwnerId() != AuthContext.userId()) { throw new AccessDeniedException("owner"); }
        return result;
    }

    @PostMapping("/mismatch/{id}")
    public int mismatch(@PathVariable("id") long id, @RequestBody CancelRequest request) {
        auth.requireOwner(id, AuthContext.userId());
        return data.cancel(request.getOrderId());
    }

    @PostMapping("/aligned/{id}")
    public int aligned(@PathVariable("id") long id, @RequestBody CancelRequest request) {
        auth.requireOwner(id, AuthContext.userId());
        return data.cancel(id);
    }

    @GetMapping("/tenant/all")
    public java.util.List<Order> tenantAll() {
        return data.all(AuthContext.tenantId());
    }

    @GetMapping("/tenant/scoped")
    public java.util.List<Order> tenantSafe() {
        return data.scoped(AuthContext.tenantId());
    }

    @GetMapping("/spoof/{id}")
    public Order spoof(@PathVariable("id") long id, @RequestParam("userId") long userId) {
        auth.requireOwner(id, userId);
        return data.get(id);
    }

    @GetMapping("/trusted/{id}")
    public Order trusted(@PathVariable("id") long id) {
        auth.requireOwner(id, AuthContext.userId());
        return data.get(id);
    }

    @PostMapping("/admin/missing/{id}")
    public int roleMissing(@PathVariable("id") long id) {
        return data.role(id);
    }

    @PreAuthorize("hasRole('ADMIN')")
    @PostMapping("/admin/safe/{id}")
    public int roleSafe(@PathVariable("id") long id) {
        return data.role(id);
    }

    @PostMapping("/ignored/{id}")
    public int ignored(@PathVariable("id") long id) {
        auth.owns(id, AuthContext.userId());
        return data.cancel(id);
    }

    @PostMapping("/enforced/{id}")
    public int enforced(@PathVariable("id") long id) {
        if (!auth.owns(id, AuthContext.userId())) { throw new AccessDeniedException("owner"); }
        return data.cancel(id);
    }

    @PostMapping("/late/{id}")
    public int late(@PathVariable("id") long id) {
        int changed = data.cancel(id);
        auth.requireOwner(id, AuthContext.userId());
        return changed;
    }

    @PostMapping("/branch/{id}")
    public int branch(@PathVariable("id") long id, @RequestParam("check") boolean check) {
        if (check) { auth.requireOwner(id, AuthContext.userId()); }
        return data.cancel(id);
    }

    @GetMapping("/sql-owner/{id}")
    public Order sqlOwner(@PathVariable("id") long id) {
        return data.owned(id, AuthContext.userId());
    }

    @GetMapping("/catalog")
    public java.util.List<Product> publicCatalog() {
        return data.products();
    }

    @GetMapping("/alias/{id}")
    public Order aliasSafe(@PathVariable("id") long id) {
        long selected = id;
        auth.requireOwner(selected, AuthContext.userId());
        return data.get(id);
    }

}
