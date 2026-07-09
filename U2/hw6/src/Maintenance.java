public class Maintenance {
    private final int elevatorId;
    private final int workerId;
    private final String toFloor;

    public Maintenance(int elevatorId, int workerId, String toFloor) {
        this.elevatorId = elevatorId;
        this.workerId = workerId;
        this.toFloor = toFloor;
    }

    public int getElevatorId() {
        return elevatorId;
    }

    public String getToFloor() {
        return toFloor;
    }

    public int getWorkerId() {
        return workerId;
    }
}
