import java.math.BigInteger;
import java.util.ArrayList;
import java.util.HashMap;

public class Poly {

    private ArrayList<Mono> monos = new ArrayList<>();

    public Poly() {
    }

    public Poly(Mono mono) {
        monos.add(mono);
    }

    public ArrayList<Mono> getMonos() {
        return monos;
    }

    public boolean isZero() {
        return monos.stream().allMatch(Mono::isZero);
    }

    public Poly add(Poly other) {
        Poly ans = new Poly();
        for (Mono mono : monos) {
            ans.addMono(mono);
        }
        for (Mono mono : other.getMonos()) {
            ans.addMono(mono);
        }
        ans.mergeLikeTerms();
        return ans;
    }

    public Poly negate() {
        Poly ans = new Poly();
        for (Mono mono : monos) {
            Mono m = new Mono(mono.getCoefficient().negate(), mono.getExponent());
            ans.addMono(m);
        }
        return ans;
    }

    public Poly multiply(Poly other) {
        Poly ans = new Poly();
        for (Mono mono1 : monos) {
            for (Mono mono2 : other.getMonos()) {
                ans.addMono(mono1.multiply(mono2));
            }
        }
        ans.mergeLikeTerms();
        return ans;
    }

    public Poly power(int exp) {
        Poly ans = new Poly(new Mono(BigInteger.ONE, 0));
        for (int i = 0; i < exp; i++) {
            ans = ans.multiply(this);
        }
        return ans;
    }

    public void addMono(Mono mono) {
        monos.add(mono);
    }

    public void mergeLikeTerms() {
        HashMap<Integer, Mono> map = new HashMap<>();
        for (Mono mono : monos) {
            map.merge(mono.getExponent(), mono,
                (oldM, newM) -> new Mono(oldM.getCoefficient().add(newM.getCoefficient()),
                    newM.getExponent()));
        }
        monos.clear();
        for (Mono mono : map.values()) {
            if (!mono.isZero()) {
                monos.add(mono);
            }
        }
    }

    @Override
    public String toString() {
        mergeLikeTerms();
        boolean isFirst = true;
        int firstPositive = -1;
        for (int i = 0; i < monos.size(); i++) {
            if (monos.get(i).isPositive()) {
                firstPositive = i;
                break;
            }
        }
        if (isZero()) {
            return "0";
        }
        StringBuilder sb = new StringBuilder();
        if (firstPositive != -1 && !monos.get(firstPositive).isZero()) {
            sb.append(monos.get(firstPositive).toString());
            isFirst = false;
        }
        for (int i = 0; i < monos.size(); i++) {
            if (i != firstPositive && !monos.get(i).isZero()) {
                String term = monos.get(i).toString();
                if (term.isEmpty()) {
                    continue;
                }
                if (isFirst) {
                    isFirst = false;
                } else {
                    if (monos.get(i).isPositive()) {
                        sb.append("+");
                    }
                }
                sb.append(term);
            }
        }
        return sb.toString();
    }
}