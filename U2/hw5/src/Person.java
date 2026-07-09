import com.oocourse.elevator1.PersonRequest;

public class Person {
    private final PersonRequest request;
    private int currentFloor;

    public Person(PersonRequest request) {
        this.request = request;
        this.currentFloor = FloorUtils.toInt(request.getFromFloor());
    }

    public int getPersonId() {
        return request.getPersonId();
    }

    public int getWeight() {
        return request.getWeight();
    }

    public int getElevatorId() {
        return request.getElevatorId();
    }

    public int getFromFloor() {
        return FloorUtils.toInt(request.getFromFloor());
    }

    public int getToFloor() {
        return FloorUtils.toInt(request.getToFloor());
    }

    public int getCurrentFloor() {
        return currentFloor;
    }
}