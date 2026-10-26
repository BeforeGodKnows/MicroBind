package demo.data;

import demo.common.*;
import org.apache.ibatis.annotations.*;
import java.util.List;
@Mapper
public interface OrderMapper {
    Order get(@Param("id") long id);
    int cancel(@Param("id") long id);
    List<Order> all(@Param("tenantId") long tenantId);
    List<Order> scoped(@Param("tenantId") long tenantId);
    Order owned(@Param("id") long id, @Param("actorId") long actorId);
    @Update("UPDATE users SET role = 'ADMIN' WHERE id = #{id}") int role(@Param("id") long id);
    @Select("SELECT id, name FROM products") List<Product> products();
    @Select("SELECT id, role FROM users WHERE id = #{id}") UserRow user(@Param("id") long id);
    @Update("UPDATE orders SET status = 'OPEN'") int resetOrders();
    @Update("UPDATE users SET role = 'USER' WHERE id IN (1,2)") int resetUsers();
}
