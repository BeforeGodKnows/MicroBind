package demo.orders;

import org.springframework.web.bind.annotation.*;
@RestController
public class Health { @GetMapping("/health") public String health() { return "ok"; } }
