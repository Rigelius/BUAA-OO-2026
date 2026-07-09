import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class IndexedList<T> {

    private final Map<T, List<Node<T>>> map = new HashMap<>();
    private Node<T> head;
    private Node<T> tail;

    public IndexedList() {
        this.head = null;
        this.tail = null;
    }

    public void addToHead(T value) {
        Node<T> newNode = new Node<>(value);
        if (head == null) {
            head = newNode;
            tail = newNode;
        } else {
            newNode.insertBefore(head);
            head = newNode;
        }
        map.computeIfAbsent(value, k -> new ArrayList<>()).add(newNode);
    }

    public void removeAll(T value) {
        List<Node<T>> nodes = map.remove(value);
        if (nodes == null) {
            return;
        }
        for (Node<T> node : nodes) {
            if (node == head) {
                head = node.getNext();
            }
            if (node == tail) {
                tail = node.getPrev();
            }
            node.remove();
        }
    }

    public boolean contains(T value) {
        List<Node<T>> nodes = map.get(value);
        return nodes != null && !nodes.isEmpty();
    }

    public List<T> getFirst(int limit) {
        List<T> ans = new ArrayList<>();
        Node<T> cur = head;
        for (int i = 0; i < limit && cur != null; i++, cur = cur.getNext()) {
            ans.add(cur.getValue());
        }
        return ans;
    }

    public List<T> toList() {
        List<T> ans = new ArrayList<>();
        Node<T> cur = head;
        while (cur != null) {
            ans.add(cur.getValue());
            cur = cur.getNext();
        }
        return ans;
    }
}
