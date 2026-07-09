import java.util.ArrayList;
import java.util.List;

public class BaseQueue {
    private final List<Person> queue = new ArrayList<>();
    private volatile boolean isEnd = false;

    public synchronized void offer(Person person) {
        queue.add(person);
        notifyAll();
    }

    public synchronized Person take() {
        if (!isEmpty()) {
            Person person = queue.get(0);
            queue.remove(person);
            return person;
        }
        return null;
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

    public synchronized int getSize() {
        return queue.size();
    }

    public synchronized List<Person> getDeepCopyQueue() {
        List<Person> copy = new ArrayList<>();
        for (Person p : queue) {
            copy.add(new Person(p));
        }
        return copy;
    }
}