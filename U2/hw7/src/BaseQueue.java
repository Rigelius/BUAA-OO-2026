import java.util.ArrayList;
import java.util.List;

public class BaseQueue {
    private final List<Person> queue = new ArrayList<>();
    private final List<List<Person>> floorQueues = new ArrayList<>(11);
    private volatile boolean isEnd = false;

    public BaseQueue() {
        for (int i = 0; i <= 10; i++) {
            floorQueues.add(new ArrayList<>());
        }
    }

    public synchronized void offer(Person person) {
        queue.add(person);
        floorQueues.get(person.getCurrentFloor()).add(person);
        notifyAll();
    }

    public synchronized Person take() {
        if (!isEmpty()) {
            Person person = queue.get(0);
            remove(person);
            return person;
        }
        return null;
    }

    public synchronized void remove(Person person) {
        queue.remove(person);
        floorQueues.get(person.getCurrentFloor()).remove(person);
    }

    public synchronized void clear() {
        queue.clear();
        for (List<Person> list : floorQueues) {
            list.clear();
        }
    }

    public synchronized boolean hasRequestAt(int floor) {
        return !floorQueues.get(floor).isEmpty();
    }

    public synchronized List<Person> getRequestAt(int floor) {
        return new ArrayList<>(floorQueues.get(floor));
    }

    public synchronized boolean isEmpty() {
        return queue.isEmpty();
    }

    public List<Person> getQueue() {
        return queue;
    }

    public synchronized boolean isEnd() {
        return isEnd;
    }

    public synchronized void setEnd(boolean isEnd) {
        this.isEnd = isEnd;
        notifyAll();
    }

    public synchronized List<Person> getDeepCopyQueue() {
        List<Person> copy = new ArrayList<>();
        for (Person p : queue) {
            copy.add(new Person(p));
        }
        return copy;
    }
}