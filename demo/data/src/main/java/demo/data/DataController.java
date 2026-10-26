package demo.data;

import demo.common.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import java.util.List;
@RestController
@RequestMapping("/internal")
public class DataController {
    @Autowired private OrderMapper mapper;
    @GetMapping("/orders/{key}") public Order get(@PathVariable("key") long recordId) { return mapper.get(recordId); }
    @PostMapping("/orders/{key}/cancel") public int cancel(@PathVariable("key") long recordId) { return mapper.cancel(recordId); }
    @GetMapping("/orders/all") public List<Order> all(@RequestParam("tenant") long scope) { return mapper.all(scope); }
    @GetMapping("/orders/scoped") public List<Order> scoped(@RequestParam("tenant") long scope) { return mapper.scoped(scope); }
    @GetMapping("/orders/owned/{key}") public Order owned(@PathVariable("key") long recordId, @RequestParam("actor") long subject) { return mapper.owned(recordId, subject); }
    @PostMapping("/users/{key}/role") public int role(@PathVariable("key") long recordId) { return mapper.role(recordId); }
    @GetMapping("/products") public List<Product> products() { return mapper.products(); }
    @GetMapping("/test/orders/{id}") public Order inspect(@PathVariable("id") long id) { return mapper.get(id); }
    @GetMapping("/test/users/{id}") public UserRow inspectUser(@PathVariable("id") long id) { return mapper.user(id); }
    @PostMapping("/test/reset") public String reset() { mapper.resetOrders(); mapper.resetUsers(); return "ok"; }
}
