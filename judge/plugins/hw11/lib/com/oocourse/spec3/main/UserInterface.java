package com.oocourse.spec3.main;
import java.util.List;

public interface UserInterface {
    /*@ public instance model int id;
      @ public instance model non_null String name;
      @ public instance model int age;
      @ public instance model int coins;
      @ public instance model non_null UserInterface[] following;
      @ public instance model non_null UserInterface[] followers;
      @ public instance model non_null int[] medals;
      @ public instance model non_null UserInterface[] contributors;
      @ public instance model non_null int[] contributions;
      @ public instance model non_null int[] receivedVideos;
      @ public instance model non_null VideoInterface[] watchedVideos;
      @ public instance model non_null VideoInterface[] likedVideos;
      @ public instance model non_null String[] types;
      @ public instance model non_null int[] typeCounts;
      @ public instance model non_null VideoInterface[] videos;
      @*/

    /*@ invariant contributors.length == contributions.length &&
      @  (\forall int i,j; 0 <= i && i < j && j < followers.length;
      @   !followers[i].equals(followers[j])) &&
      @  (\forall int i,j; 0 <= i && i < j && j < following.length;
      @   !following[i].equals(following[j])) &&
      @ invariant (\forall int i, j; 0 <= i && i < j && j < watchedVideos.length;
      @              !watchedVideos[i].equals(watchedVideos[j]));
      @  types.length == 7 &&
      @  types[0].equals("tech") && types[1].equals("music") && types[2].equals("sport") && types[3].equals("game") &&
      @  types[4].equals("food") && types[5].equals("travel") && types[6].equals("comedy") &&
      @  typeCounts.length == types.length &&
      @  (\forall int i; 0 <= i < typeCounts.length;typeCounts[i] >= 0);
      @*/

    //@ ensures \result == id;
    public /*@ pure @*/ int getId();

    //@ ensures \result == name;
    public /*@ pure @*/ String getName();

    //@ ensures \result == age;
    public /*@ pure @*/ int getAge();

    /*@ public normal_behavior
      @ assignable \nothing;
      @ ensures \result == (\exists int i; 0 <= i && i < following.length;
      @                     following[i].getId() == user.getId());
      @*/
    public /*@ pure @*/ boolean isFollowing(UserInterface user);

    /*@ public normal_behavior
      @ assignable \nothing;
      @ ensures \result == (\exists int i; 0 <= i && i < followers.length;
      @                     followers[i].getId() == user.getId());
      @*/
    public /*@ pure @*/ boolean containsFollower(UserInterface user);

    /*@ public normal_behavior
      @ assignable \nothing;
      @ ensures \result == (\exists int i; 0 <= i && i < receivedVideos.length;
      @                     receivedVideos[i] == video.getId());
      @*/
    public /*@ pure @*/ boolean hasReceivedVideo(VideoInterface video);

    /*@ public normal_behavior
      @ requires followers.length == 0;
      @ assignable \nothing;
      @ ensures \result != null && \result.length == 4;
      @ ensures (\forall int i; 0 <= i && i < 4; \result[i] == 0.0);
      @ also
      @ public normal_behavior
      @ requires followers.length > 0;
      @ assignable \nothing;
      @ ensures \result != null && \result.length == 4;
      @ ensures \result[0] == 1.00 * (\num_of int k; 0 <= k < followers.length; followers[k].getAge() <= 16) / followers.length;
      @ ensures \result[1] == 1.00 * (\num_of int k; 0 <= k < followers.length; followers[k].getAge() >= 17 && followers[k].getAge() <= 30) / followers.length;
      @ ensures \result[2] == 1.00 * (\num_of int k; 0 <= k < followers.length; followers[k].getAge() >= 31 && followers[k].getAge() <= 45) / followers.length;
      @ ensures \result[3] == 1.00 * (\num_of int k; 0 <= k < followers.length; followers[k].getAge() >= 46) / followers.length;
      @*/
    public /*@ pure @*/ double[] queryAgeRatio();

    /*@ public normal_behavior
      @ assignable \nothing;
      @ ensures \result != null;
      @ ensures (\forall int i; 0 <= i && i < receivedVideos.length && i <= 4;
      @           \result.contains(receivedVideos[i]) && \result.get(i) == receivedVideos[i]);
      @ ensures \result.size() == ((receivedVideos.length < 5) ? receivedVideos.length: 5);
     */
    public /*@ pure @*/ List<Integer> queryReceivedUnwatchedVideos();

    /*@ public normal_behavior
      @ assignable \nothing;
      @ ensures \result == (\exists int i; 0 <= i && i < watchedVideos.length;
      @                     watchedVideos[i].getId() == video.getId());
      @*/
    public /*@ pure @*/ boolean hasWatchedVideo(VideoInterface video);

    /*@ public normal_behavior
      @ assignable \nothing;
      @ ensures \result == (\exists int i; 0 <= i && i < likedVideos.length;
      @                     likedVideos[i].getId() == video.getId());
      @*/
    public /*@ pure @*/ boolean hasLikedVideo(VideoInterface video);

    //@ ensures \result == coins;
    public /*@ pure @*/int getCoins();

    /*@ public normal_behavior
      @ assignable \nothing;
      @ ensures \result == (\exists int i; 0 <= i && i < medals.length;
      @                     medals[i] == uploaderId);
      @*/
    public /*@ pure @*/ boolean hasMedal(int uploaderId);

    /*@ public normal_behavior
      @ requires (\exists int i; 0 <= i && i < types.length; types[i].equals(type));
      @ ensures (\exists int i; 0 <= i && i < types.length;
      @             types[i].equals(type) &&
      @              \result == typeCounts[i] * (totalVideos - watchedVideos.length + 1));
      @*/
    
    public /*@ pure @*/ int getInterest(String type, int totalVideos);
    
    /*@ public normal_behavior
      @ assignable \nothing;
      @ ensures \result == (\sum int i; 0 <= i && i < videos.length && videos[i].getType().equals(type); videos[i].getHeat());
      @*/
    public /*@ pure @*/ int getInfluence(String type);

    /*@ public normal_behavior
      @ assignable \nothing
      @ ensures \result.size() == types.length;
      @ ensures (\forall int i; 0 <= i < \result.size(); \result.get(i) == getInterest(types[i], totalVideos));
     */
    public /*@ pure @*/ List<Integer> getProfile(int totalVideos);

    /*@ public normal_behavior
      @ ensures \result == (\sum int typeIdx; 0 <= typeIdx < types.length;
      @                     getInterest(types[typeIdx], totalVideos) * up.getInfluence(types[typeIdx]));
     */
    public /*@ pure @*/ long computeUpScore(UserInterface up, int totalVideos);

    /*@ public normal_behavior
      @ requires obj != null && obj instanceof UserInterface;
      @ assignable \nothing;
      @ ensures \result == (((UserInterface) obj).getId() == id);
      @ also
      @ public normal_behavior
      @ requires obj == null || !(obj instanceof UserInterface);
      @ assignable \nothing;
      @ ensures \result == false;
      @*/
    public /*@ pure @*/ boolean equals(Object obj);
}