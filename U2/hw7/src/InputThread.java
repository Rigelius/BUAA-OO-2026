import com.oocourse.elevator3.ElevatorInput;
import com.oocourse.elevator3.Request;
import com.oocourse.elevator3.PersonRequest;
import com.oocourse.elevator3.MaintRequest;
import com.oocourse.elevator3.UpdateRequest;
import com.oocourse.elevator3.RecycleRequest;

import java.io.IOException;
import java.util.List;

public class InputThread extends Thread {
    private final ScheduleQueue scheduleQueue;
    private final List<ElevatorShaft> shafts;

    public InputThread(ScheduleQueue scheduleQueue, List<ElevatorShaft> shafts) {
        this.scheduleQueue = scheduleQueue;
        this.shafts = shafts;
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
                MaintRequest maintRequest = (MaintRequest) request;
                Maintenance maint = new Maintenance(
                    maintRequest.getElevatorId(),
                    maintRequest.getWorkerId(),
                    maintRequest.getToFloor()
                );
                shafts.get(maintRequest.getElevatorId() - 1).receiveMaintenance(maint);
            } else if (request instanceof UpdateRequest) {
                UpdateRequest updateRequest = (UpdateRequest) request;
                shafts.get(updateRequest.getElevatorId() - 1).receiveUpdate();
            } else if (request instanceof RecycleRequest) {
                RecycleRequest recycleRequest = (RecycleRequest) request;
                shafts.get(recycleRequest.getElevatorId() - 7).receiveRecycle();
            }
        }
        try {
            input.close();
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }
}