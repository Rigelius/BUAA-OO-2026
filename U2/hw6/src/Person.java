import com.oocourse.elevator2.PersonRequest;

public class Person {
    private final PersonRequest request;
    private int currentFloor;
    private int elevatorId;

    public Person(PersonRequest request) {
        this.request = request;
        this.currentFloor = FloorUtils.toInt(request.getFromFloor());
    }

    public Person(Person other) {
        this.request = other.request;
        this.currentFloor = other.currentFloor;
        this.elevatorId = other.elevatorId;
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
        return FloorUtils.toInt(request.getToFloor());
    }

    public int getCurrentFloor() {
        return currentFloor;
    }

    public void setCurrentFloor(int currentFloor) {
        this.currentFloor = currentFloor;
    }
}