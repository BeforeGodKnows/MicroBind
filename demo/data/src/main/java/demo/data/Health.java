package demo.data;

import org.springframework.web.bind.annotation.*;
@RestController
public class Health { @GetMapping("/health") public String health() { return "ok"; } }
