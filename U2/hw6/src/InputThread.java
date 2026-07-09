import com.oocourse.elevator2.ElevatorInput;
import com.oocourse.elevator2.MaintRequest;
import com.oocourse.elevator2.PersonRequest;
import com.oocourse.elevator2.Request;

import java.io.IOException;
import java.util.List;

public class InputThread extends Thread {
    private final ScheduleQueue scheduleQueue;
    private final List<ElevatorThread> elevators;

    public InputThread(ScheduleQueue scheduleQueue, List<ElevatorThread> elevators) {
        this.scheduleQueue = scheduleQueue;
        this.elevators = elevators;
    }

    @Override
    public void run() {
        ElevatorInput input = new ElevatorInput(System.in);
        while (true) {
            Request request = input.nextRequest();
            if (request == null) {
                scheduleQueue.setEnd(true);
                break;
            } else if (request instanceof PersonRequest) {
                Person person = new Person((PersonRequest) request);
                scheduleQueue.offer(person);
            } else if (request instanceof MaintRequest) {
                MaintRequest maintReq = (MaintRequest) request;
                Maintenance maint = new Maintenance(
                    maintReq.getElevatorId(),
                    maintReq.getWorkerId(),
                    maintReq.getToFloor()
                );
                elevators.get(maintReq.getElevatorId() - 1).receiveMaintenance(maint);
            }
        }
        try {
            input.close();
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }
}