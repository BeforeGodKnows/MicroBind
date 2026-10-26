package demo.orders;

import demo.common.*;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.*;
import java.util.List;
@FeignClient(name="data", url="${lab.data-url}", path="/internal")
public interface DataClient {
    @GetMapping("/orders/{objectId}") Order get(@PathVariable("objectId") long id);
    @PostMapping("/orders/{objectId}/cancel") int cancel(@PathVariable("objectId") long id);
    @GetMapping("/orders/all") List<Order> all(@RequestParam("tenant") long tenantId);
    @GetMapping("/orders/scoped") List<Order> scoped(@RequestParam("tenant") long tenantId);
    @GetMapping("/orders/owned/{objectId}") Order owned(@PathVariable("objectId") long id, @RequestParam("actor") long actorId);
    @PostMapping("/users/{userId}/role") int role(@PathVariable("userId") long id);
    @GetMapping("/products") List<Product> products();
}
