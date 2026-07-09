import com.oocourse.elevator3.TimableOutput;

import java.util.ArrayList;
import java.util.List;

public class MainClass {
    public static void main(String[] args) {
        TimableOutput.initStartTimestamp();
        ScheduleQueue scheduleQueue = new ScheduleQueue();
        List<ElevatorShaft> shafts = new ArrayList<>();

        for (int i = 1; i <= 6; i++) {
            ElevatorShaft shaft = new ElevatorShaft(i, scheduleQueue);
            shafts.add(shaft);
            shaft.getMainCar().start();
            shaft.getSubCar().start();
        }

        DispatchThread dispatchThread = new DispatchThread(scheduleQueue, shafts);
        dispatchThread.start();

        InputThread inputThread = new InputThread(scheduleQueue, shafts);
        inputThread.start();
    }
}