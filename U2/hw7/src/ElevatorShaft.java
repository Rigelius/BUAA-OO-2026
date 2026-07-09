import java.util.concurrent.locks.ReentrantLock;

public class ElevatorShaft {
    private final ElevatorThread mainCar;
    private final ElevatorThread subCar;
    private final ReentrantLock f2Lock = new ReentrantLock(true);
    private final ScheduleQueue scheduleQueue;
    private volatile ShaftState state = ShaftState.NORMAL;
    private volatile Maintenance maint = null;
    private volatile long maintAcceptTime = 0;
    private volatile long updateAcceptTime = 0;
    private volatile long recycleAcceptTime = 0;

    public ElevatorShaft(int shaftId, ScheduleQueue scheduleQueue) {
        this.scheduleQueue = scheduleQueue;
        this.mainCar = new ElevatorThread(shaftId, this, new ProcessQueue(), scheduleQueue, true);
        this.subCar = new ElevatorThread(
            shaftId + 6, this, new ProcessQueue(), scheduleQueue, false
        );
    }

    public synchronized void receiveMaintenance(Maintenance maint) {
        this.maint = maint;
        this.maintAcceptTime = System.currentTimeMillis();
        this.state = ShaftState.REP_ACCEPT;
        synchronized (mainCar.getProcessQueue()) {
            mainCar.getProcessQueue().notifyAll();
        }
    }

    public synchronized void receiveUpdate() {
        this.updateAcceptTime = System.currentTimeMillis();
        this.state = ShaftState.UP_ACCEPT;
        synchronized (mainCar.getProcessQueue()) {
            mainCar.getProcessQueue().notifyAll();
        }
    }

    public synchronized void receiveRecycle() {
        this.recycleAcceptTime = System.currentTimeMillis();
        this.state = ShaftState.REC_ACCEPT;
        synchronized (subCar.getProcessQueue()) {
            subCar.getProcessQueue().notifyAll();
        }
    }

    public Maintenance getMaint() {
        return maint;
    }

    public long getMaintAcceptTime() {
        return maintAcceptTime;
    }

    public long getRecycleAcceptTime() {
        return recycleAcceptTime;
    }

    public ScheduleQueue getScheduleQueue() {
        return scheduleQueue;
    }

    public ShaftState getState() {
        return state;
    }

    public void setState(ShaftState state) {
        this.state = state;
    }

    public long getUpdateAcceptTime() {
        return updateAcceptTime;
    }

    public ReentrantLock getF2Lock() {
        return f2Lock;
    }

    public ElevatorThread getMainCar() {
        return mainCar;
    }

    public ElevatorThread getSubCar() {
        return subCar;
    }

    public void clearMaint() {
        this.maint = null;
    }
}
