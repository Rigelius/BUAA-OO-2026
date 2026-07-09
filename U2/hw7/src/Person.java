import com.oocourse.elevator3.PersonRequest;

public class Person {
    private final PersonRequest request;
    private final int destFloor;
    private int currentFloor;
    private int elevatorId;
    private int transferFloor = -1;

    public Person(PersonRequest request) {
        this.request = request;
        currentFloor = FloorUtils.toInt(request.getFromFloor());
        destFloor = FloorUtils.toInt(request.getToFloor());
    }

    public Person(Person other) {
        this.request = other.request;
        this.currentFloor = other.currentFloor;
        this.elevatorId = other.elevatorId;
        this.destFloor = other.destFloor;
        this.transferFloor = other.transferFloor;
    }

    public void setTransferFloor(int transferFloor) {
        this.transferFloor = transferFloor;
    }

    public boolean needsTransfer() {
        return transferFloor != -1;
    }

    public int getPersonId() {
        return request.getPersonId();
    }

    public int getWeight() {
        return request.getWeight();
    }

    public int getElevatorId() {
        return elevatorId;
    }

    public void setElevatorId(int elevatorId) {
        this.elevatorId = elevatorId;
    }

    public int getFromFloor() {
        return currentFloor;
    }

    public int getToFloor() {
        return needsTransfer() ? transferFloor : destFloor;
    }

    public int getCurrentFloor() {
        return currentFloor;
    }

    public void setCurrentFloor(int currentFloor) {
        this.currentFloor = currentFloor;
    }

    public int getDestFloor() {
        return destFloor;
    }

    public void completeTransfer() {
        this.currentFloor = this.transferFloor;
        this.transferFloor = -1;
    }
}