package demo.common;

public class Order {
    private long id;
    public long getId() { return id; }
    public void setId(long value) { this.id = value; }
    private long ownerId;
    public long getOwnerId() { return ownerId; }
    public void setOwnerId(long value) { this.ownerId = value; }
    private long tenantId;
    public long getTenantId() { return tenantId; }
    public void setTenantId(long value) { this.tenantId = value; }
    private String status;
    public String getStatus() { return status; }
    public void setStatus(String value) { this.status = value; }
    private String address;
    public String getAddress() { return address; }
    public void setAddress(String value) { this.address = value; }
}
